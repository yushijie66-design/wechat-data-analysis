import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - v15.0 (大单逻辑回归：仅按份数)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro Max", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **v15.0升级：【有效大单】仅统计单笔购买份数 > 1 的订单；保留智能刷单剔除功能。**")

# 1. 文件上传
uploaded_file = st.file_uploader("请将 CSV 或 Excel 文件拖入下方框中", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # ==========================================
        # 1️⃣ 数据读取
        # ==========================================
        if uploaded_file.name.endswith('.csv'):
            try:
                raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                raw_df = pd.read_csv(uploaded_file, encoding='gbk')
        else:
            raw_df = pd.read_excel(uploaded_file)

        # ==========================================
        # 2️⃣ 基础预处理
        # ==========================================
        raw_df['商品售后'] = raw_df['商品售后'].fillna('无')
        raw_df['商品名称'] = raw_df['商品名称'].fillna('未知商品')
        raw_df['订单状态'] = raw_df['订单状态'].fillna('未知')
        
        # 自动识别商家编码
        code_col = '商品编码(自定义)'
        if code_col not in raw_df.columns:
            possible_cols = ['商家编码', 'SKU编码(自定义)']
            for col in possible_cols:
                if col in raw_df.columns:
                    code_col = col
                    break
        
        if code_col in raw_df.columns:
            raw_df[code_col] = raw_df[code_col].fillna('未标记渠道')
            raw_df[code_col] = raw_df[code_col].astype(str).replace(['nan', ''], '未标记渠道')

        # 数值转换
        cols_to_numeric = ['商品数量', '商品已退款金额', '商品实际价格(总共)', '订单实际支付金额']
        for col in cols_to_numeric:
            if col in raw_df.columns:
                raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)
            else:
                raw_df[col] = 0

        if '商品数量' not in raw_df.columns:
            raw_df['商品数量'] = 1

        # ==========================================
        # 3️⃣ 🕵️‍♂️ 智能刷单识别 (精准版)
        # ==========================================
        if '收件人手机' in raw_df.columns:
            raw_df['clean_phone'] = raw_df['收件人手机'].astype(str).str.strip()
        else:
            raw_df['clean_phone'] = raw_df['收件人姓名'].astype(str)

        raw_df['is_refund_flag'] = (
            (raw_df['商品售后'].str.contains('退款完成', na=False)) | 
            (raw_df['商品已退款金额'] > 0)
        )

        # 统计行为
        user_stats = raw_df.groupby('clean_phone').agg(
            total_count=('订单号', 'count'),
            refund_count=('is_refund_flag', 'sum')
        ).reset_index()

        # 判定刷单：下单 >=3 且 退款率 >= 80%
        brushing_users = user_stats[
            (user_stats['total_count'] >= 3) & 
            ((user_stats['refund_count'] / user_stats['total_count']) >= 0.8)
        ]
        
        brushing_phones = brushing_users['clean_phone'].tolist()

        # 数据隔离
        brushing_df = raw_df[raw_df['clean_phone'].isin(brushing_phones)].copy()
        clean_df = raw_df[~raw_df['clean_phone'].isin(brushing_phones)].copy()
        
        removed_orders_count = len(brushing_df)

        # 刷单警告
        if not brushing_df.empty:
            st.warning(f"⚠️ **已智能剔除刷单数据**：共发现 **{len(brushing_users)}** 个异常手机号，涉及 **{removed_orders_count}** 个订单。")
            with st.expander("🔍 点击查看刷单“黑名单”"):
                st.dataframe(brushing_users.rename(columns={'clean_phone':'手机号', 'total_count':'总单数', 'refund_count':'退款数'}))

        # ==========================================
        # 4️⃣ 构建分析数据集 (Paid Orders)
        # ==========================================
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

        # ==========================================
        # 5️⃣ 核心指标计算
        # ==========================================
        total_real_orders = len(paid_orders)
        total_real_gmv = paid_orders['商品实际价格(总共)'].sum()
        
        refund_orders = paid_orders[paid_orders['是否退款']]
        refund_count = len(refund_orders)
        refund_amount = refund_orders['商品已退款金额'].sum()

        to_ship_count = len(clean_df[clean_df['订单状态'] == '待发货'])
        to_ship_amount = clean_df[clean_df['订单状态'] == '待发货']['商品实际价格(总共)'].sum()
        
        shipped_df = clean_df[clean_df['订单状态'].isin(['已发货', '已完成'])]
        shipped_count = len(shipped_df)
        shipped_amount = shipped_df['商品实际价格(总共)'].sum()

        rate_count = (refund_count / total_real_orders * 100) if total_real_orders > 0 else 0
        rate_amount = (refund_amount / total_real_gmv * 100) if total_real_gmv > 0 else 0

        # ==========================================
        # 📊 模块展示
        # ==========================================

        # --- 模块1：核心看板 ---
        st.markdown(f"### 💰 核心经营数据 (已剔除 {removed_orders_count} 条刷单)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 支付总单量", f"{total_real_orders}")
        c2.metric("💰 支付总金额", f"¥ {total_real_gmv:,.0f}")
        c3.metric("📉 订单退款率", f"{rate_count:.2f}%")
        c4.metric("💸 金额退款率", f"{rate_amount:.2f}%")
        st.markdown("---")
        
        k1, k2, k3 = st.columns(3)
        k1.info(f"**⏳ 待发货**: {to_ship_count} 单 (¥{to_ship_amount:,.0f})")
        k2.success(f"**🚚 已发货**: {shipped_count} 单 (¥{shipped_amount:,.0f})")
        k3.error(f"**❌ 已退款**: {refund_count} 单 (¥{refund_amount:,.0f})")
        st.divider()

        # --- 模块2：渠道业绩透视 ---
        st.markdown(f"### 🎬 主播/渠道业绩透视 (已剔除 {removed_orders_count} 条刷单)")
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
                    "金额退款率": st.column_config.TextColumn("金额退款率 ⚠️"),
                },
                use_container_width=True
            )
        else:
            st.warning("⚠️ 未找到商家编码列。")
        st.divider()

        # --- 模块3：有效大单与复购 ---
        st.markdown(f"### 🛍️ 大单与复购分析 (已剔除 {removed_orders_count} 条刷单)")
        valid_orders_df = paid_orders[paid_orders['是否有效']].copy()
        
        col_left, col_right = st.columns(2)
        with col_left:
            # 🔥 回归纯份数逻辑
            st.markdown("#### 有效大单 (净成交)")
            st.caption("判定标准：单笔购买份数 > 1 (即 ≥ 2份)")
            
            multi = valid_orders_df[valid_orders_df['商品数量'] > 1]
            
            if not multi.empty:
                st.info(f"发现 **{len(multi)}** 个有效大单")
                multi = multi.sort_values(by='商品数量', ascending=False)
                st.dataframe(
                    multi[['商品数量', '商品名称', '收件人姓名', '订单实际支付金额', code_col]], 
                    hide_index=True,
                    column_config={
                        "商品数量": st.column_config.NumberColumn("份数", format="%d 份")
                    }
                )
            else:
                st.success("暂无。")

        with col_right:
            st.markdown("#### 有效复购 (回头客)")
            if '收件人手机' in clean_df.columns:
                valid_orders_df['clean_phone'] = valid_orders_df['收件人手机'].astype(str).str.strip()
                counts = valid_orders_df['clean_phone'].value_counts()
                repeat = counts[counts > 1]
                
                if not repeat.empty:
                    st.warning(f"发现 **{len(repeat)}** 位回头客")
                    rep_list = []
                    for phone, cnt in repeat.items():
                        r = valid_orders_df[valid_orders_df['clean_phone'] == phone].iloc[0]
                        rep_list.append({
                            "收件人": r['收件人姓名'], 
                            "手机": str(r['收件人手机'])[-4:], 
                            "单数": cnt
                        })
                    st.dataframe(pd.DataFrame(rep_list), hide_index=True)
                else:
                    st.success("暂无。")

        st.divider()

        # --- 模块4：商品总榜 ---
        st.markdown(f"### 🏆 商品销售总榜 (已剔除 {removed_orders_count} 条刷单)")
        prod_stats = paid_orders.groupby('商品名称').agg({
            '订单号': 'count',
            '商品数量': 'sum',
            '商品已退款金额': 'sum',
            '商品实际价格(总共)': 'sum'
        }).rename(columns={'订单号': '支付单数(含退)', '商品数量': '销售总份数'})
        
        prod_stats['金额退款率'] = (prod_stats['商品已退款金额'] / prod_stats['商品实际价格(总共)'] * 100).fillna(0)
        ref_cnt = paid_orders[paid_orders['是否退款']].groupby('商品名称')['订单号'].count()
        prod_stats['退款单数'] = ref_cnt.fillna(0)
        prod_stats['单量退款率'] = (prod_stats['退款单数'] / prod_stats['支付单数(含退)'] * 100).fillna(0)
        
        prod_stats = prod_stats.sort_values(by='销售总份数', ascending=False)
        
        d_df = prod_stats.copy()
        d_df['金额退款率'] = d_df['金额退款率'].apply(lambda x: f"{x:.2f}%")
        d_df['单量退款率'] = d_df['单量退款率'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(d_df[['支付单数(含退)', '销售总份数', '单量退款率', '金额退款率']], use_container_width=True)

    except Exception as e:
        st.error(f"分析出错: {e}")

