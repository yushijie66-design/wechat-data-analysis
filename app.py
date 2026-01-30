import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - v8.0 (修正退款在已取消里的问题)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro Max", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **已修正逻辑：包含【已取消但退款成功】的订单，准确计算渠道退款率。**")

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

        # 4. 全局核心指标 (顶部看板)
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
        # 🔥 模块2：主播/渠道业绩分析 (修正版)
        # ==========================================
        st.markdown("### 🎬 主播/渠道业绩透视 (按商家编码)")
        st.caption("✅ **统计逻辑已修正**：只要【付过款】就算入统计（无论状态是否为已取消）。这样【付款后退款】的订单也会正确计入退款率。")

        if code_col in df.columns:
            # ----------------------------------------------------
            # 核心修正：如何筛选“付过款”的订单？
            # 1. 订单实际支付金额 > 0 (正常付款)
            # 2. 或者 商品已退款金额 > 0 (付款后全额退款，可能支付金额显式为0或被退回，但退款金额会有记录)
            # 3. 或者 状态是 待发货/已发货/已完成 (肯定付过款)
            # ----------------------------------------------------
            
            is_paid = (df['订单实际支付金额'] > 0) | \
                      (df['商品已退款金额'] > 0) | \
                      (df['订单状态'].isin(['待发货', '已发货', '已完成']))
            
            # 拿到所有“真金白银”相关的单子
            paid_orders = df[is_paid].copy()
            
            # 在这些单子里，标记谁退款了
            paid_orders['是否退款'] = (paid_orders['商品售后'].str.contains('退款完成', na=False)) | (paid_orders['商品已退款金额'] > 0)
            
            # 标记谁是有效成交 (付过款 且 没退款)
            paid_orders['是否有效'] = ~paid_orders['是否退款']

            # 按渠道分组统计
            channel_stats = paid_orders.groupby(code_col).apply(
                lambda x: pd.Series({
                    '有效成交单数': x[x['是否有效']]['订单号'].count(),      # 净单量
                    '有效成交金额': x[x['是否有效']]['商品实际价格(总共)'].sum(), # 净营收
                    '退款单数': x[x['是否退款']]['订单号'].count(),        # 退款单量
                    '退款金额': x['商品已退款金额'].sum(),                 # 退款金额
                    '总GMV': x['商品实际价格(总共)'].sum()                 # 分母：总销售额
                })
            ).reset_index()

            # 计算退款率 = 退款金额 / 总GMV
            channel_stats['金额退款率'] = (channel_stats['退款金额'] / channel_stats['总GMV'] * 100).fillna(0)

            # 排序
            channel_stats = channel_stats.sort_values(by='有效成交金额', ascending=False)
            
            # 格式化
            channel_display = channel_stats.copy()
            channel_display['金额退款率'] = channel_display['金额退款率'].apply(lambda x: f"{x:.2f}%")
            channel_display['有效成交金额'] = channel_display['有效成交金额'].apply(lambda x: f"¥{x:,.0f}")
            channel_display['退款金额'] = channel_display['退款金额'].apply(lambda x: f"¥{x:,.0f}")
            channel_display['有效成交单数'] = channel_display['有效成交单数'].astype(int)

            st.dataframe(
                channel_display[['商品编码(自定义)', '有效成交单数', '有效成交金额', '退款单数', '退款金额', '金额退款率']],
                column_config={
                    "商品编码(自定义)": st.column_config.TextColumn("渠道/主播编码"),
                    "有效成交单数": st.column_config.NumberColumn("有效成交 (净)", help="实际发货且未退款的单量"),
                    "有效成交金额": st.column_config.TextColumn("有效营收 (净) 💰
