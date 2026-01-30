import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - v12.0 (全链路数据清洗版)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro Max", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **数据一致性校验：刷单数据将在所有板块（包括渠道、商品、明细）中被彻底剔除。**")

# 1. 文件上传
uploaded_file = st.file_uploader("请将 CSV 或 Excel 文件拖入下方框中", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # ==========================================
        # 1️⃣ 数据读取 (Raw Data)
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
        # 填充缺失值
        raw_df['商品售后'] = raw_df['商品售后'].fillna('无')
        raw_df['商品名称'] = raw_df['商品名称'].fillna('未知商品')
        raw_df['订单状态'] = raw_df['订单状态'].fillna('未知')
        
        # 自动识别商家编码列
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

        # 数值列强制转换
        cols_to_numeric = ['商品数量', '商品已退款金额', '商品实际价格(总共)', '订单实际支付金额']
        for col in cols_to_numeric:
            if col in raw_df.columns:
                raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)
            else:
                raw_df[col] = 0

        if '商品数量' not in raw_df.columns:
            raw_df['商品数量'] = 1

        # ==========================================
        # 3️⃣ 🕵️‍♂️ 刷单识别与剔除 (Cleaning Phase)
        # ==========================================
        
        # 构造用户ID (去除空格防止误差)
        if '收件人姓名' in raw_df.columns and '收件人手机' in raw_df.columns:
            raw_df['user_id'] = raw_df['收件人姓名'].astype(str).str.strip() + "|" + raw_df['收件人手机'].astype(str).str.strip()
        else:
            raw_df['user_id'] = raw_df.index.astype(str)

        # 标记是否退款
        raw_df['is_refund_flag'] = (
            (raw_df['商品售后'].str.contains('退款完成', na=False)) | 
            (raw_df['商品已退款金额'] > 0)
        )

        # 统计用户行为
        user_stats = raw_df.groupby('user_id').agg(
            total_count=('订单号', 'count'),
            refund_count=('is_refund_flag', 'sum')
        ).reset_index()

        # 判定刷单：次数 >=3 且 退款率100%
        brushing_users = user_stats[
            (user_stats['total_count'] >= 3) & 
            (user_stats['total_count'] == user_stats['refund_count'])
        ]
        brushing_user_ids = brushing_users['user_id'].tolist()

        # 🔥【关键步骤】生成 clean_df
        # 只有 clean_df 才会被用于后续的所有分析！
        brushing_df = raw_df[raw_df['user_id'].isin(brushing_user_ids)].copy()
        clean_df = raw_df[~raw_df['user_id'].isin(brushing_user_ids)].copy()

        # 记录剔除数量
        removed_count = len(brushing_df)
        removed_users = len(brushing_users)

        # 展示刷单警告
        if not brushing_df.empty:
            st.warning(f"⚠️ **已全链路剔除刷单数据**：共隔离 **{removed_users}** 人，涉及 **{removed_count}** 个订单。")
            with st.expander("查看被剔除的刷单明细 (这些数据将不会出现在下方任何图表中)"):
                st.dataframe(brushing_df[['订单号', '收件人姓名', '商品名称', '订单实际支付金额', '商品已退款金额', code_col]])
        else:
            st.success("✅ 数据检测完毕：未发现【下单≥3次且全退】的刷单数据。")

        # ==========================================
        # 4️⃣ 构建分析数据集 (Paid Orders)
        # ==========================================
        # 注意：这里使用的是 clean_df，确保源头干净
        
        real_paid_mask = (
            clean_df['订单状态'].isin(['待发货', '已发货', '已完成']) |
            (clean_df['商品已退款金额'] > 0) |
            (clean_df['商品售后'].str.contains('退款完成', na=False))
        )
        
        # 这里的 paid_orders 已经是剔除了刷单数据的“真实支付订单”
        paid_orders = clean_df[real_paid_mask].copy()
        
        # 标记属性
        paid_orders['是否退款'] = (
            (paid_orders['商品售后'].str.contains('退款完成', na=False)) | 
            (paid_orders['商品已退款金额'] > 0)
        )
        paid_orders['是否有效'] = ~paid_orders['是否退款']

        # ==========================================
        # 5️⃣ 核心指标计算 (基于 clean_df)
        # ==========================================
        total_real_orders = len(paid_orders)
        total_real_gmv = paid_orders['商品实际价格(总共)'].sum()
        
        refund_orders = paid_orders[paid_orders['是否退款']]
        refund_count = len(refund_orders)
        refund_amount = refund_orders['商品已退款金额'].sum()

        # 物流统计 (基于 clean_df)
        to_ship_count = len(clean_df[clean_df['订单状态'] == '待发货'])
        to_ship_amount = clean_df[clean_df['订单状态'] == '待发货']['商品实际价格(总共)'].sum()
        
        shipped_df = clean_df[clean_df['订单状态'].isin(['已发货', '已完成'])]
        shipped_count = len(shipped_df)
        shipped_amount = shipped_df['商品实际价格(总共)'].sum()

        rate_count = (refund_count / total_real_orders * 100) if total_real_orders > 0 else 0
        rate_amount = (refund_amount / total_real_gmv * 100) if total_real_gmv > 0 else 0

        # ==========================================
        # 📊 模块展示 (All Verified Clean)
        # ==========================================

        # --- 模块1：核心看板 ---
        st.markdown(f"### 💰 核心经营数据 (已剔除 {removed_count} 条刷单)")
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
        st.markdown(f"### 🎬 主播/渠道业绩透视 (已剔除 {removed_count} 条刷单)")
        st.caption("✅ 数据源确认：统计数据已完全排除刷单样本。")

        if code_col in clean_df.columns:
            # 这里的 paid_orders 已经不含刷单数据
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
                    "金额退款率": st.column_config.TextColumn("退款率 ⚠️"),
                },
                use_container_width=True
            )
        else:
            st.warning("⚠️ 未找到商家编码列。")
        st.divider()

        # --- 模块3：有效大单与复购 ---
        st.markdown(f"### 🛍️ 大单与复购分析 (已剔除 {removed_count} 条刷单)")
        valid_orders_df = paid_orders[paid_orders['是否有效']].copy()
        
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("#### 有效大单 (净成交)")
            multi = valid_orders_df[valid_orders_df['商品数量'] > 1]
            if not multi.empty:
                st.info(f"发现 **{len(multi)}** 个有效大单")
                st.dataframe(multi[['商品数量', '商品名称', '收件人姓名', '订单实际支付金额', code_col]], hide_index=True)
            else:
                st.success("暂无。")

        with col_right:
            st.markdown("#### 有效复购 (回头客)")
            if '收件人姓名' in clean_df.columns:
                clean_df['cid'] = clean_df['收件人姓名'].astype(str) + clean_df['收件人手机'].astype(str)
                # 复购我们只看有效成交的
                valid_orders_df['cid'] = valid_orders_df['收件人姓名'].astype(str) + valid_orders_df['收件人手机'].astype(str)
                counts = valid_orders_df['cid'].value_counts()
                repeat = counts[counts > 1]
                if not repeat.empty:
                    st.warning(f"发现 **{len(repeat)}** 位回头客")
                    rep_list = []
                    for cid, cnt in repeat.items():
                        r = valid_orders_df[valid_orders_df['cid'] == cid].iloc[0]
                        rep_list.append({"收件人": r['收件人姓名'], "手机": str(r['收件人手机'])[-4:], "单数": cnt})
                    st.dataframe(pd.DataFrame(rep_list), hide_index=True)
                else:
                    st.success("暂无。")

        st.divider()

        # --- 模块4：商品总榜 ---
        st.markdown(f"### 🏆 商品销售总榜 (已剔除 {removed_count} 条刷单)")
        prod_stats = paid_orders.groupby('商品名称').agg({
            '订单号': 'count',
            '商品数量': 'sum',
            '商品已退款金额': 'sum',
            '商品实际价格(总共)': 'sum'
        }).rename(columns={'订单号': '支付单数(含退)', '商品数量': '销售总份数'})
        
        prod_stats['金额退款率'] = (prod_stats['商品已退款金额'] / prod_stats['商品实际价格(总共)'] * 100).fillna(0)
        # 单量退款率
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
