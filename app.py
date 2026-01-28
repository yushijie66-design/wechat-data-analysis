import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - 最终完整版 (含金额退款率)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **拖入表格，自动分析成交、发货、以及【按金额】和【按单量】的双重退款率。**")

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
        # 填充文本列
        df['商品售后'] = df['商品售后'].fillna('无')
        df['商品名称'] = df['商品名称'].fillna('未知商品')
        
        # 核心：确保金额和数量列是数字格式 (关键步骤)
        # 微信导出的金额列可能带符号，或者为空，需要强制转数字
        cols_to_numeric = ['商品数量', '商品已退款金额', '商品实际价格(总共)', '订单实际支付金额']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0  # 如果列不存在，设为0防止报错

        # 4. 核心指标统计
        total_orders = len(df)                                     # 总单数
        total_gmv = df['商品实际价格(总共)'].sum()                  # 总成交金额 (按商品总价算)
        
        # 筛选退款数据
        # 逻辑：只要"商品已退款金额"大于0，或者售后状态显示退款，都算有退款
        refund_mask = (df['商品售后'].str.contains('退款完成', na=False)) | (df['商品已退款金额'] > 0)
        refund_df = df[refund_mask]
        
        refund_orders_count = len(refund_df)                       # 退款单数
        refund_total_amount = df['商品已退款金额'].sum()            # 退款总金额

        # 计算双重退款率
        rate_by_count = (refund_orders_count / total_orders * 100) if total_orders > 0 else 0
        rate_by_amount = (refund_total_amount / total_gmv * 100) if total_gmv > 0 else 0

        # --- 顶部数据看板 ---
        st.markdown("### 💰 资金与订单概览")
        
        # 第一行：资金维度
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总成交金额", f"¥ {total_gmv:,.0f}")
        c2.metric("累计退款金额", f"¥ {refund_total_amount:,.0f}", delta_color="inverse")
        c3.metric("📉 金额退款率", f"{rate_by_amount:.2f}%", help="公式：总退款金额 / 总成交金额")
        c4.metric("实收金额 (预估)", f"¥ {total_gmv - refund_total_amount:,.0f}")

        # 第二行：订单维度
        st.markdown("---")
        d1, d2, d3, d4 = st.columns(4)
        shipped_count = len(df[df['订单状态'] == '已发货'])
        to_ship_count = len(df[df['订单状态'] == '待发货'])
        
        d1.metric("总订单量", f"{total_orders} 单")
        d2.metric("已发货", f"{shipped_count} 单")
        d3.metric("待发货", f"{to_ship_count} 单", delta_color="inverse")
        d4.metric("📦 订单退款率", f"{rate_by_count:.2f}%", help="公式：退款单数 / 总订单数")

        st.divider()

        # --- 5. 商品深度排行榜 ---
        st.markdown("### 🏆 单品销售 & 双维退款分析")
        
        # 按商品聚合统计
        product_analysis = df.groupby('商品名称').agg({
            '订单号': 'count',                       # 销量(单)
            '商品数量': 'sum',                       # 销量(份)
            '商品实际价格(总共)': 'sum',             # 总销售额
            '商品已退款金额': 'sum'                  # 总退款额
        }).rename(columns={
            '订单号': '成交单数',
            '商品数量': '销售份数',
            '商品实际价格(总共)': '成交总金额',
            '商品已退款金额': '退款总金额'
        })

        # 计算每个商品的两个退款率
        product_analysis['金额退款率'] = (product_analysis['退款总金额'] / product_analysis['成交总金额'] * 100).fillna(0)
        
        # 为了计算单量退款率，我们需要单独统计每个商品的退款单数
        refund_counts = df[refund_mask].groupby('商品名称')['订单号'].count()
        product_analysis['退款单数'] = refund_counts
        product_analysis['退款单数'] = product_analysis['退款单数'].fillna(0) # 没退款的补0
        product_analysis['单量退款率'] = (product_analysis['退款单数'] / product_analysis['成交单数'] * 100).fillna(0)

        # 排序：按成交金额从高到低
        product_analysis = product_analysis.sort_values(by='成交总金额', ascending=False)

        # 格式化显示 (百分比和金额符号)
        display_df = product_analysis.copy()
        display_df['金额退款率'] = display_df['金额退款率'].apply(lambda x: f"{x:.2f}%")
        display_df['单量退款率'] = display_df['单量退款率'].apply(lambda x: f"{x:.2f}%")
        display_df['成交总金额'] = display_df['成交总金额'].apply(lambda x: f"¥{x:,.0f}")
        display_df['退款总金额'] = display_df['退款总金额'].apply(lambda x: f"¥{x:,.0f}")

        # 展示表格
        st.dataframe(
            display_df[['成交单数', '销售份数', '成交总金额', '退款总金额', '金额退款率', '单量退款率']],
            column_config={
                "金额退款率": st.column_config.TextColumn("金额退款率 💰", help="该商品退款金额占销售额的比例"),
                "单量退款率": st.column_config.TextColumn("单量退款率 📦", help="该商品退款单数占总单数的比例"),
            },
            use_container_width=True
        )

    except Exception as e:
        st.error(f"分析出错: {e}")
        st.info("提示：请确保上传的表格包含【商品已退款金额】和【商品实际价格(总共)】这两列。")