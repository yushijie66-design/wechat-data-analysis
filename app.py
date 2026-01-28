import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 微信小店数据分析工具 - 增强版 (含多单透视 & 复购检测)
# -------------------------------------------------------------------

st.set_page_config(page_title="微信小店数据分析助手 Pro Max", layout="wide")

st.title("📊 微信小店深度销售分析")
st.markdown("👉 **拖入表格，自动透视【一次买多份】的大客户和【重复下单】的回头客。**")

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
        
        # 强制转数字，防止报错
        cols_to_numeric = ['商品数量', '商品已退款金额', '商品实际价格(总共)', '订单实际支付金额']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        # 如果没有数量列，默认设为1
        if '商品数量' not in df.columns:
            df['商品数量'] = 1

        # 4. 基础指标
        total_orders = len(df)
        total_gmv = df['商品实际价格(总共)'].sum()
        refund_mask = (df['商品售后'].str.contains('退款完成', na=False)) | (df['商品已退款金额'] > 0)
        refund_df = df[refund_mask]
        refund_total_amount = df['商品已退款金额'].sum()
        
        # 计算退款率
        rate_by_amount = (refund_total_amount / total_gmv * 100) if total_gmv > 0 else 0

        # --- 顶部看板 ---
        st.markdown("### 💰 资金与订单概览")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总成交金额", f"¥ {total_gmv:,.0f}")
        c2.metric("实收金额 (预估)", f"¥ {total_gmv - refund_total_amount:,.0f}")
        c3.metric("总订单量", f"{total_orders} 单")
        c4.metric("金额退款率", f"{rate_by_amount:.2f}%")
        
        st.divider()

        # ==========================================
        # 🔥 新增功能区：多单与复购分析
        # ==========================================
        
        col_left, col_right = st.columns(2)

        # --- 左侧：一次买多份 (大单分析) ---
        with col_left:
            st.markdown("### 🛍️ 单次购买多份 (大单)")
            # 逻辑修改：只要数量 > 1 就算多份
            multi_item_orders = df[df['商品数量'] > 1].copy()
            
            if not multi_item_orders.empty:
                count_multi = len(multi_item_orders)
                st.info(f"发现 **{count_multi}** 个订单含有多份商品：")
                
                # 按数量从多到少排序
                multi_item_orders = multi_item_orders.sort_values(by='商品数量', ascending=False)
                
                # 整理显示列
                show_cols = ['商品数量', '商品名称', '收件人姓名', '订单实际支付金额']
                valid_cols = [c for c in show_cols if c in df.columns]
                
                st.dataframe(
                    multi_item_orders[valid_cols],
                    column_config={
                        "商品数量": st.column_config.NumberColumn("份数", format="%d 份"),
                        "订单实际支付金额": st.column_config.NumberColumn("金额", format="¥%d"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("✅ 暂无购买多份的订单 (大家都是买1份)。")

        # --- 右侧：同一个人下多单 (复购分析) ---
        with col_right:
            st.markdown("### 🔄 疑似重复下单/复购")
            # 逻辑：根据【收件人姓名 + 收件人手机】判断是不是同一个人
            if '收件人姓名' in df.columns and '收件人手机' in df.columns:
                # 组合姓名和手机号作为唯一标识
                df['客户标识'] = df['收件人姓名'].astype(str) + df['收件人手机'].astype(str)
                
                # 统计每个人的下单次数
                customer_counts = df['客户标识'].value_counts()
                # 找出下单次数 > 1 的人
                repeat_customers = customer_counts[customer_counts > 1]
                
                if not repeat_customers.empty:
                    st.warning(f"发现 **{len(repeat_customers)}** 位客户下了多个订单：")
                    
                    # 准备展示数据
                    repeat_list = []
                    for cust_id, count in repeat_customers.items():
                        # 找到这个人的第一条记录，获取姓名手机
                        record = df[df['客户标识'] == cust_id].iloc[0]
                        repeat_list.append({
                            "收件人": record['收件人姓名'],
                            "手机尾号": str(record['收件人手机'])[-4:], # 只看后4位
                            "下单次数": count
                        })
                    
                    repeat_df = pd.DataFrame(repeat_list)
                    st.dataframe(
                        repeat_df,
                        column_config={
                            "下单次数": st.column_config.NumberColumn("单数", format="%d 单"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("✅ 暂无重复下单的客户。")
            else:
                st.write("⚠️ 表格中缺少【收件人姓名】或【手机】列，无法分析复购。")

        st.divider()

        # --- 底部：商品总榜 ---
        st.markdown("### 🏆 商品销售总榜")
        product_analysis = df.groupby('商品名称').agg({
            '订单号': 'count',
            '商品数量': 'sum',
            '商品已退款金额': 'sum',
            '商品实际价格(总共)': 'sum'
        }).rename(columns={'订单号': '成交单数', '商品数量': '销售总份数'})
        
        # 计算金额退款率
        product_analysis['金额退款率'] = (product_analysis['商品已退款金额'] / product_analysis['商品实际价格(总共)'] * 100).fillna(0)
        product_analysis = product_analysis.sort_values(by='销售总份数', ascending=False)

        # 格式化
        display_df = product_analysis.copy()
        display_df['金额退款率'] = display_df['金额退款率'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(
            display_df[['成交单数', '销售总份数', '金额退款率']], 
            use_container_width=True
        )

    except Exception as e:
        st.error(f"分析出错: {e}")
