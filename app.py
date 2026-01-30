import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - v9.0 (渠道分析：总支付+净成交 双维度)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro Max", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **新增：渠道分析同时展示【支付总单量(含退)】和【实际净成交(扣退)】，满足不同考核需求。**")

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

        # 3. 数据清洗
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

        # 4. 全局核心指标
        total_orders = len(df)
        total_gmv = df['商品实际价格(总共)'].sum() 

        # 退款逻辑
        refund_mask = (df['商品售后'].str.contains('退款完成', na=False)) | (df['商品已退款金额'] > 0)
        refund_df = df[refund_mask]
        refund_count = len(refund_df)
        refund_amount = df['商品已退款金额'].sum()

        # 物流逻辑
        to_ship_df = df[df['订单状态'] == '待发货']
        to_ship_count = len(to_ship_df)
        to_ship_amount = to_ship_df['商品实际价格(总共)'].sum()

        shipped_df = df[df['订单状态'].isin(['已发货', '已完成'])]
        shipped_count = len(shipped_df)
        shipped_amount = shipped_df['商品实际价格(总共)'].sum()

        # 退款率
        rate_count = (refund_count / total_orders * 100) if total_orders > 0 else 0
        rate_amount = (refund_amount / total_gmv * 100) if total_gmv > 0 else 0

        # ==========================================
        # 🔥 模块1：核心看板
        # ==========================================
        st.markdown("### 💰 核心经营数据详解")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 总订单量 (含无效)", f"{total_orders} 单")
        c2.metric("💰 总成交金额 (GMV)", f"¥ {total_gmv:,.0f}")
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
        # 🔥 模块2：主播/渠道业绩透视 (双维度展示)
        # ==========================================
        st.markdown("### 🎬 主播/渠道业绩透视 (按商家编码)")
        st.caption("✅ **已优化字段名**：【支付总单量】包含退款（看带货能力），【实际净成交】扣除退款（看实际业绩）。")

        if code_col in df.columns:
            # 1. 筛选“真金白银”付过款的订单 (排除未付款取消)
            is_paid = (df['订单实际支付金额'] > 0) | \
                      (df['商品已退款金额'] > 0) | \
                      (df['订单状态'].isin(['待发货', '已发货', '已完成']))
            
            paid_orders = df[is_paid].copy()
            
            # 2. 标记退款
            paid_orders['是否退款'] = (paid_orders['商品售后'].str.contains('退款完成', na=False)) | (paid_orders['商品已退款金额'] > 0)
            
            # 3. 标记净成交 (付了钱且没退)
            paid_orders['是否有效'] = ~paid_orders['是否退款']

            # 4. 分组统计
            channel_stats = paid_orders.groupby(code_col).apply(
                lambda x: pd.Series({
                    '支付总单量(含退)': x['订单号'].count(),                 # 只要付过钱就算
                    '支付总金额(含退)': x['商品实际价格(总共)'].sum(),      # 总GMV
                    
                    '实际净成交(扣退)': x[x['是否有效']]['订单号'].count(), # 扣除退款后的
                    '实际净营收(扣退)': x[x['是否有效']]['商品实际价格(总共)'].sum(),
                    
                    '退款单数': x[x['是否退款']]['订单号'].count(),
                    '退款金额': x['商品已退款金额'].sum()
                })
            ).reset_index()

            # 5. 计算退款率
            channel_stats['金额退款率'] = (channel_stats['退款金额'] / channel_stats['支付总金额(含退)'] * 100).fillna(0)

            # 6. 排序 (按支付总金额排序，看谁带货猛)
            channel_stats = channel_stats.sort_values(by='支付总金额(含退)', ascending=False)
            
            # 7. 格式化
            channel_display = channel_stats.copy()
            channel_display['金额退款率'] = channel_display['金额退款率'].apply(lambda x: f"{x:.2f}%")
            
            for col in ['支付总金额(含退)', '实际净营收(扣退)', '退款金额']:
                channel_display[col] = channel_display[col].apply(lambda x: f"¥{x:,.0f}")
            
            for col in ['支付总单量(含退)', '实际净成交(扣退)', '退款单数']:
                channel_display[col] = channel_display[col].astype(int)

            # 8. 展示表格 (列出所有关键数据)
            st.dataframe(
                channel_display[['商品编码(自定义)', '支付总单量(含退)', '支付总金额(含退)', '实际净成交(扣退)', '实际净营收(扣退)', '金额退款率']],
                column_config={
                    "商品编码(自定义)": st.column_config.TextColumn("渠道/主播"),
                    "支付总单量(含退)": st.column_config.NumberColumn("支付单量 (含退)", help="只要付过款都算，包含后续退款的"),
                    "支付总金额(含退)": st.column_config.TextColumn("支付金额 (含退)"),
                    "实际净成交(扣退)": st.column_config.NumberColumn("净成交 (实)", help="扣除退款后的实际发货单量"),
                    "实际净营收(扣退)": st.column_config.TextColumn("净营收 (实)"),
                    "金额退款率": st.column_config.TextColumn("退款率 ⚠️"),
                },
                use_container_width=True
            )
        else:
            st.warning("⚠️ 表格中未找到【商品编码(自定义)】列，无法自动分析渠道业绩。")

        st.divider()

        # ==========================================
        # 🔥 模块3：有效大单与复购分析 (逻辑保持一致)
        # ==========================================
        # 这里的“有效”指的是：已付款
        # 如果你想看【含退款】的大单，可以用 paid_orders
        # 如果你想看【净成交】的大单，可以用 paid_orders[paid_orders['是否有效']]
        # 既然是分析“大客户”，通常建议看【净成交】（退了的不算大客户）
        
        valid_orders_df = paid_orders[paid_orders['是否有效']].copy()

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### 🛍️ 有效大单 (已付款且无退款)")
            multi_item_orders = valid_orders_df[valid_orders_df['商品数量'] > 1]
            if not multi_item_orders.empty:
                st.info(f"发现 **{len(multi_item_orders)}** 个有效大单：")
                multi_item_orders = multi_item_orders.sort_values(by='商品数量', ascending=False)
                show_cols = ['商品数量', '商品名称', '收件人姓名', '订单实际支付金额', code_col]
                valid_cols = [c for c in show_cols if c in df.columns]
                st.dataframe(multi_item_orders[valid_cols], use_container_width=True, hide_index=True)
            else:
                st.success("✅ 暂无购买多份的有效订单。")

        with col_right:
            st.markdown("### 🔄 有效复购 (回头客)")
            if '收件人姓名' in df.columns and '收件人手机' in df.columns:
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
        # 🔥 模块4：商品总榜
        # ==========================================
        st.markdown("### 🏆 商品销售总榜")
        product_analysis = df.groupby('商品名称').agg({
            '订单号': 'count',
            '商品数量': 'sum',
            '商品已退款金额': 'sum',
            '商品实际价格(总共)': 'sum'
        }).rename(columns={'订单号': '成交单数', '商品数量': '销售总份数'})
        
        product_analysis['金额退款率'] = (product_analysis['商品已退款金额'] / product_analysis['商品实际价格(总共)'] * 100).fillna(0)
        refund_counts_by_product = df[refund_mask].groupby('商品名称')['订单号'].count()
        product_analysis['退款单数'] = refund_counts_by_product.fillna(0)
        product_analysis['单量退款率'] = (product_analysis['退款单数'] / product_analysis['成交单数'] * 100).fillna(0)
        
        product_analysis = product_analysis.sort_values(by='销售总份数', ascending=False)
        
        display_df = product_analysis.copy()
        display_df['金额退款率'] = display_df['金额退款率'].apply(lambda x: f"{x:.2f}%")
        display_df['单量退款率'] = display_df['单量退款率'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(display_df[['成交单数', '销售总份数', '单量退款率', '金额退款率']], use_container_width=True)

    except Exception as e:
        st.error(f"分析出错: {e}")
