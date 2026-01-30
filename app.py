import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - v11.0 (智能清洗刷单数据版)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro Max", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **v11.0升级：自动识别并剔除【下单≥3次且全额退款】的刷单数据，还原真实业绩。**")

# 1. 文件上传
uploaded_file = st.file_uploader("请将 CSV 或 Excel 文件拖入下方框中", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # 2. 读取文件
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='gbk')
        else:
            df = pd.read_excel(uploaded_file)

        # 3. 基础数据清洗
        df['商品售后'] = df['商品售后'].fillna('无')
        df['商品名称'] = df['商品名称'].fillna('未知商品')
        df['订单状态'] = df['订单状态'].fillna('未知')
        
        # 自动识别商家编码列
        code_col = '商品编码(自定义)'
        if code_col not in df.columns:
            possible_cols = ['商家编码', 'SKU编码(自定义)']
            for col in possible_cols:
                if col in df.columns:
                    code_col = col
                    break
        
        if code_col in df.columns:
            df[code_col] = df[code_col].fillna('未标记渠道')
            df[code_col] = df[code_col].astype(str).replace(['nan', ''], '未标记渠道')

        # 数值列强制转换
        cols_to_numeric = ['商品数量', '商品已退款金额', '商品实际价格(总共)', '订单实际支付金额']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        if '商品数量' not in df.columns:
            df['商品数量'] = 1

        # ==========================================
        # 🕵️‍♂️ 核心功能：智能识别刷单数据
        # ==========================================
        
        # 1. 构造用户唯一标识 (姓名+手机)
        if '收件人姓名' in df.columns and '收件人手机' in df.columns:
            df['user_id'] = df['收件人姓名'].astype(str) + "|" + df['收件人手机'].astype(str)
        else:
            df['user_id'] = df.index.astype(str) # 如果没有用户信息，就无法识别

        # 2. 标记每一单是否退款
        df['is_refund_flag'] = (
            (df['商品售后'].str.contains('退款完成', na=False)) | 
            (df['商品已退款金额'] > 0)
        )

        # 3. 按用户分组统计
        user_stats = df.groupby('user_id').agg(
            total_count=('订单号', 'count'),          # 总下单次数
            refund_count=('is_refund_flag', 'sum')    # 退款次数
        ).reset_index()

        # 4. 识别刷单党：下单次数 >= 3 且 退款次数 == 下单次数 (全退)
        brushing_users = user_stats[
            (user_stats['total_count'] >= 3) & 
            (user_stats['total_count'] == user_stats['refund_count'])
        ]
        
        brushing_user_ids = brushing_users['user_id'].tolist()
        
        # 5. 数据隔离 (切分数据)
        brushing_df = df[df['user_id'].isin(brushing_user_ids)].copy()
        clean_df = df[~df['user_id'].isin(brushing_user_ids)].copy() # 干净的数据

        # ==========================================
        # 📢 刷单数据隔离区 (放在最上方展示)
        # ==========================================
        if not brushing_df.empty:
            brushing_orders_count = len(brushing_df)
            brushing_users_count = len(brushing_users)
            
            st.warning(f"⚠️ **已检测并剔除刷单数据**：共发现 **{brushing_users_count}** 人，涉及 **{brushing_orders_count}** 个订单。")
            
            with st.expander("查看被剔除的刷单明细 (点击展开)"):
                st.markdown(f"**判定标准**：单人下单次数 ≥ 3次，且全部退款。")
                
                # 展示刷单用户列表
                st.markdown("#### 👤 刷单人员名单")
                st.dataframe(
                    brushing_users.rename(columns={'user_id': '用户标识', 'total_count': '刷单次数', 'refund_count': '退款次数'}),
                    use_container_width=True,
                    hide_index=True
                )
                
                # 展示刷单订单明细
                st.markdown("#### 🧾 被剔除的订单明细")
                st.dataframe(
                    brushing_df[['订单号', '收件人姓名', '商品名称', '订单实际支付金额', '订单状态', '商品售后']],
                    use_container_width=True
                )
        else:
            st.success("✅ 未检测到符合特征的刷单数据 (下单≥3次且全退)。")

        # ==========================================
        # 🚀 以下所有分析均使用 clean_df (干净数据)
        # ==========================================
        
        # 重新定义 real_paid_mask (基于 clean_df)
        real_paid_mask = (
            clean_df['订单状态'].isin(['待发货', '已发货', '已完成']) |
            (clean_df['商品已退款金额'] > 0) |
            (clean_df['商品售后'].str.contains('退款完成', na=False))
        )
        
        paid_orders = clean_df[real_paid_mask].copy()
        
        paid_orders['是否退款'] = (
            (paid_orders['商品售后'].str.contains('退款完成', na=False)) | 
            (paid_orders['商品已退款金额'] > 0)
        )
        paid_orders['是否有效'] = ~paid_orders['是否退款']

        # 全局指标 (Clean Data)
        total_real_orders = len(paid_orders)
        total_real_gmv = paid_orders['商品实际价格(总共)'].sum()
        
        refund_orders = paid_orders[paid_orders['是否退款']]
        refund_count = len(refund_orders)
        refund_amount = refund_orders['商品已退款金额'].sum()

        # 物流统计
        to_ship_df = clean_df[clean_df['订单状态'] == '待发货']
        to_ship_count = len(to_ship_df)
        to_ship_amount = to_ship_df['商品实际价格(总共)'].sum()

        shipped_df = clean_df[clean_df['订单状态'].isin(['已发货', '已完成'])]
        shipped_count = len(shipped_df)
        shipped_amount = shipped_df['商品实际价格(总共)'].sum()

        # 退款率
        rate_count = (refund_count / total_real_orders * 100) if total_real_orders > 0 else 0
        rate_amount = (refund_amount / total_real_gmv * 100) if total_real_gmv > 0 else 0

        # ==========================================
        # 🔥 模块1：核心看板 (干净版)
        # ==========================================
        st.markdown("### 💰 核心经营数据 (已剔除刷单)")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 支付总单量", f"{total_real_orders} 单")
        c2.metric("💰 支付总金额", f"¥ {total_real_gmv:,.0f}")
        c3.metric("📉 订单退款率", f"{rate_count:.2f}%")
        c4.metric("💸 金额退款率", f"{rate_amount:.2f}%")

        st.markdown("---")

        k1, k2, k3 = st.columns(3)
        with k1:
            st.info(f"**⏳ 待发货 (急)**")
            st.write(f"数量：**{to_ship_count}** 单")
            st.write(f"金额：**¥ {to_ship_amount:,.0f}**")
        with k2:
            st.success(f"**🚚 已发货 / 已完成**")
            st.write(f"数量：**{shipped_count}** 单")
            st.write(f"金额：**¥ {shipped_amount:,.0f}**")
        with k3:
            st.error(f"**❌ 已退款**")
            st.write(f"数量：**{refund_count}** 单")
            st.write(f"金额：**¥ {refund_amount:,.0f}**")

        st.divider()

        # ==========================================
        # 🔥 模块2：主播/渠道业绩透视 (干净版)
        # ==========================================
        st.markdown("### 🎬 主播/渠道业绩透视 (按商家编码)")
        
        if code_col in clean_df.columns:
            channel_stats = paid_orders.groupby(code_col).apply(
                lambda x: pd.Series({
                    '支付总单量(含退)': x['订单号'].count(),
                    '支付总金额(含退)': x['商品实际价格(总共)'].sum(),
                    '实际净成交(扣退)': x[x['是否有效']]['订单号'].count(),
                    '实际净营收(扣退)': x[x['是否有效']]['商品实际价格(总共)'].sum(),
                    '退款单数': x[x['是否退款']]['订单号'].count(),
                    '退款金额': x['商品已退款金额'].sum()
                })
            ).reset_index()

            channel_stats['金额退款率'] = (channel_stats['退款金额'] / channel_stats['支付总金额(含退)'] * 100).fillna(0)
            channel_stats = channel_stats.sort_values(by='支付总金额(含退)', ascending=False)
            
            # 格式化
            channel_display = channel_stats.copy()
            channel_display['金额退款率'] = channel_display['金额退款率'].apply(lambda x: f"{x:.2f}%")
            for col in ['支付总金额(含退)', '实际净营收(扣退)', '退款金额']:
                channel_display[col] = channel_display[col].apply(lambda x: f"¥{x:,.0f}")
            for col in ['支付总单量(含退)', '实际净成交(扣退)', '退款单数']:
                channel_display[col] = channel_display[col].astype(int)

            st.dataframe(
                channel_display[['商品编码(自定义)', '支付总单量(含退)', '支付总金额(含退)', '实际净成交(扣退)', '实际净营收(扣退)', '金额退款率']],
                column_config={
                    "商品编码(自定义)": st.column_config.TextColumn("渠道/主播"),
                    "实际净成交(扣退)": st.column_config.NumberColumn("净成交 (实)"),
                    "金额退款率": st.column_config.TextColumn("退款率 ⚠️"),
                },
                use_container_width=True
            )
        else:
            st.warning("⚠️ 表格中未找到【商品编码(自定义)】列，无法自动分析渠道业绩。")

        st.divider()

        # ==========================================
        # 🔥 模块3：有效大单与复购分析 (干净版)
        # ==========================================
        valid_orders_df = paid_orders[paid_orders['是否有效']].copy()
        
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### 🛍️ 有效大单 (净成交)")
            multi_item_orders = valid_orders_df[valid_orders_df['商品数量'] > 1]
            if not multi_item_orders.empty:
                st.info(f"发现 **{len(multi_item_orders)}** 个有效大单：")
                multi_item_orders = multi_item_orders.sort_values(by='商品数量', ascending=False)
                show_cols = ['商品数量', '商品名称', '收件人姓名', '订单实际支付金额', code_col]
                valid_cols = [c for c in show_cols if c in clean_df.columns]
                st.dataframe(multi_item_orders[valid_cols], use_container_width=True, hide_index=True)
            else:
                st.success("✅ 暂无购买多份的有效订单。")

        with col_right:
            st.markdown("### 🔄 有效复购 (回头客)")
            if '收件人姓名' in clean_df.columns and '收件人手机' in clean_df.columns:
                clean_df['客户标识'] = clean_df['收件人姓名'].astype(str) + clean_df['收件人手机'].astype(str)
                # 注意：这里统计复购，应该在【净成交】里统计，还是在【所有支付订单】里统计？
                # 通常看回头客是看成交的，所以用 valid_orders_df
                if '客户标识' not in valid_orders_df.columns:
                     valid_orders_df['客户标识'] = valid_orders_df['收件人姓名'].astype(str) + valid_orders_df['收件人手机'].astype(str)
                
                customer_counts = valid_orders_df['客户标识'].value_counts()
                repeat_customers = customer_counts[customer_counts > 1]
                
                if not repeat_customers.empty:
                    st.warning(f"发现 **{len(repeat_customers)}** 位高价值回头客：")
                    repeat_list = []
                    for cust_id, count in repeat_customers.items():
                        record = valid_orders_df[valid_orders_df['客户标识'] == cust_id].iloc[0]
                        repeat_list.append({
                            "收件人": record['收件人姓名'],
                            "手机尾号": str(record['收件人手机'])[-4:], 
                            "有效成交单数": count
                        })
                    st.dataframe(pd.DataFrame(repeat_list), hide_index=True, use_container_width=True)
                else:
                    st.success("✅ 暂无有效复购客户。")
            else:
                st.write("⚠️ 缺少客户信息列。")

        st.divider()

        # ==========================================
        # 🔥 模块4：商品总榜 (干净版)
        # ==========================================
        st.markdown("### 🏆 商品销售总榜")
        product_analysis = paid_orders.groupby('商品名称').agg({
            '订单号': 'count',
            '商品数量': 'sum',
            '商品已退款金额': 'sum',
            '商品实际价格(总共)': 'sum'
        }).rename(columns={'订单号': '支付单数(含退)', '商品数量': '销售总份数'})
        
        product_analysis['金额退款率'] = (product_analysis['商品已退款金额'] / product_analysis['商品实际价格(总共)'] * 100).fillna(0)
        refund_counts = paid_orders[paid_orders['是否退款']].groupby('商品名称')['订单号'].count()
        product_analysis['退款单数'] = refund_counts.fillna(0)
        product_analysis['单量退款率'] = (product_analysis['退款单数'] / product_analysis['支付单数(含退)'] * 100).fillna(0)
        
        product_analysis = product_analysis.sort_values(by='销售总份数', ascending=False)
        
        display_df = product_analysis.copy()
        display_df['金额退款率'] = display_df['金额退款率'].apply(lambda x: f"{x:.2f}%")
        display_df['单量退款率'] = display_df['单量退款率'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(display_df[['支付单数(含退)', '销售总份数', '单量退款率', '金额退款率']], use_container_width=True)

    except Exception as e:
        st.error(f"分析出错: {e}")
