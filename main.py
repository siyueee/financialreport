import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, date
from pathlib import Path
import json

# ======================== 【密码验证功能】 ========================
# def check_password():
#     """返回 True 如果用户输入了正确的密码"""
#     def password_entered():
#         if st.session_state["password"] == "wujialingshizhu":  # 这里改成你想要的密码
#             st.session_state["password_correct"] = True
#         del st.session_state["password"]
#
#     if "password_correct" not in st.session_state:
#         st.title("🔒 访问授权验证")
#         st.text_input("请输入访问密码", type="password", on_change=password_entered, key="password")
#         return False
#     elif not st.session_state["password_correct"]:
#         st.title("🔒 访问授权验证")
#         st.text_input("❌ 密码错误，请重新输入", type="password", on_change=password_entered, key="password")
#         return False
#     else:
#         return True
#
# # 验证密码，不通过则不显示后面内容
# if not check_password():
#     st.stop()
# ==================================================================
# --- 1. 页面配置 ---
st.set_page_config(page_title="商业化运营全维度监控", layout="wide")

# --- 样式优化：整合卡片效果 + 消除顶部空白 + 吸顶固定 ---
st.markdown("""
    <style>
    /* 1. 消除页面顶部大空白 */
    .block-container {
        padding-top: 1rem !important;    /* 默认是 6rem，压缩到 1rem */
        padding-bottom: 0rem !important;
        max-width: 95%;                  /* 适当加宽页面利用率 */
    }

    /* 隐藏顶部装饰横条 */
    [data-testid="stHeader"] {
        height: 0px;
        display: none;
    }

    /* 2. 你原本的卡片样式 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); 
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricValue"] > div {
        color: #1E40AF !important; 
    }
    div[data-testid="stMetricLabel"] > div > p {
        color: #475569 !important;
        font-weight: 600;
    }

    /* 3. 让这排指标卡横向容器置顶固定 (Sticky) */
    [data-testid="stAppViewBlockContainer"] {
        overflow: visible !important;
    }

    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {
        position: -webkit-sticky;
        position: sticky;
        top: 0rem;      /* 因为 header 删了，直接贴顶 */
        z-index: 1000;
        background-color: white; /* 滚动时背景不透明 */
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        border-bottom: 1px solid #f0f2f6;
    }
    </style>
    """, unsafe_allow_html=True)


# --- 2. 数据处理引擎 ---
@st.cache_data
def load_data(uploaded_file):
    try:
        # 1. 读取上传的文件
        df = pd.read_excel(uploaded_file, sheet_name='数据源')

        # 2. 核心：从 JSON 读取并映射“产品系列”
        mapping_path = Path("mapping.json")
        if mapping_path.exists():
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    series_data = json.load(f)
                # 转换字典结构：{产品: 系列}
                reverse_map = {item: series for series, items in series_data.items() for item in items}
                df['产品系列'] = df['产品'].map(reverse_map).fillna("其他系列")
            except Exception as json_e:
                st.sidebar.error(f"JSON解析出错: {json_e}")
                df['产品系列'] = "格式错误"
        else:
            df['产品系列'] = "未分类"
            # 仅在初次加载且没找到文件时提示
            st.sidebar.warning("⚠️ 未找到 mapping.json")

        # 3. 日期清洗与类型对齐
        df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        df = df.dropna(subset=['日期'])
        df['日期_dt'] = df['日期'].dt.date

        # 4. 数值清洗
        for col in ['收入', '成本']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # 5. 衍生指标计算
        df['利润'] = df['收入'] - df['成本']
        df['ROI'] = df.apply(lambda r: r['收入'] / r['成本'] if r['成本'] > 0 else 0.0, axis=1)

        # 6. 默认达标逻辑
        df['是否达标'] = df['ROI'] >= 1.2

        return df

    except Exception as e:
        st.error(f"数据加载失败: {e}")
        return pd.DataFrame()

def reset_filters():
    for key in st.session_state.keys():
        if key.endswith('_filter'):
            st.session_state[key] = []

# --- 3. 主程序逻辑 ---
# 🔥 核心修改：本地文件 → 上传文件
st.sidebar.markdown("---")
st.sidebar.title("📁 数据上传")
uploaded_file = st.sidebar.file_uploader("上传 Excel 数据文件", type=["xlsx", "xls"])

if uploaded_file is not None:
    df_raw = load_data(uploaded_file)

    if not df_raw.empty:
        # --- 侧边栏筛选 ---
        st.sidebar.header("🔍 维度筛选")
        st.sidebar.button("🧹 一键重置筛选", on_click=reset_filters)

        # 日期筛选
        min_date, max_date = df_raw['日期_dt'].min(), df_raw['日期_dt'].max()
        date_sel = st.sidebar.date_input("选择日期范围", [min_date, max_date])

        # 处理日期范围对比逻辑（同比/环比基础）
        if isinstance(date_sel, (list, tuple)) and len(date_sel) == 2:
            start_date, end_date = date_sel
            days_diff = (end_date - start_date).days + 1
            prev_start = start_date - timedelta(days=days_diff)
            prev_end = start_date - timedelta(days=1)

            curr_df = df_raw[(df_raw['日期_dt'] >= start_date) & (df_raw['日期_dt'] <= end_date)]
            prev_df = df_raw[(df_raw['日期_dt'] >= prev_start) & (df_raw['日期_dt'] <= prev_end)]
        else:
            curr_df = df_raw.copy()
            prev_df = pd.DataFrame()

        # --- 业务维度筛选 (级联内嵌逻辑) ---
        st.sidebar.subheader("📌 业务维度")

        # 1. 核心修复：在循环前先定义好初始的 filtered_df
        filtered_df = curr_df.copy()
        compare_df = prev_df.copy() if not prev_df.empty else pd.DataFrame()

        # 定义内嵌关系的维度顺序
        dims = ['部门', '平台', '渠道类型', '客户','产品系列', '产品', '类型']

        # 用于级联显示的临时数据集，初始等于当前范围数据
        cascade_df = filtered_df.copy()

        for col in dims:
            if col in df_raw.columns:
                # 待选项 options 始终基于上一轮过滤后的结果 (cascade_df)
                raw_options = cascade_df[col].dropna().unique()
                options = sorted([str(opt) for opt in raw_options])

                sel = st.sidebar.multiselect(f"选择{col}", options, key=f"{col}_filter")

                if sel:
                    # 更新当前数据范围
                    filtered_df = filtered_df[filtered_df[col].astype(str).isin(sel)]
                    # 更新级联参考数据集（供下一个循环的 options 使用）
                    cascade_df = cascade_df[cascade_df[col].astype(str).isin(sel)]

                    if not compare_df.empty:
                        compare_df = compare_df[compare_df[col].astype(str).isin(sel)]
                else:
                    # 如果当前维度没选，下游维度的选项依然基于当前的 cascade_df
                    pass

            # --- 此时 filtered_df 已经完全定义好，下方的指标计算就不会报错了 ---
        # --- 4. 仪表盘渲染 ---
        st.title("🛰️ 商业化运营全维度监控看板")

        # 指标行
        st.markdown("---")
        m1, m2, m3, m4, m6 = st.columns(5)


        def calc_delta(curr, prev):
            if prev == 0 or prev is None: return None
            return f"{(curr - prev) / prev:+.2%}"


        cur_inc = filtered_df['收入'].sum()
        pre_inc = compare_df['收入'].sum() if not compare_df.empty else 0
        m1.metric("总收入", f"¥{cur_inc:,.0f}", calc_delta(cur_inc, pre_inc))

        cur_cost = filtered_df['成本'].sum()
        pre_cost = compare_df['成本'].sum() if not compare_df.empty else 0
        m2.metric("总成本", f"¥{cur_cost:,.0f}", calc_delta(cur_cost, pre_cost))

        cur_profit = filtered_df['利润'].sum()
        pre_profit = compare_df['利润'].sum() if not compare_df.empty else 0
        m3.metric("总利润", f"¥{cur_profit:,.0f}", calc_delta(cur_profit, pre_profit))

        cur_roi = cur_inc / cur_cost if cur_cost > 0 else 0
        pre_roi = pre_inc / pre_cost if pre_cost > 0 else 0
        m4.metric("整体ROI", f"{cur_roi:.2f}", calc_delta(cur_roi, pre_roi))


        # 计算当前筛选下的产品总数
        product_count = filtered_df['产品'].nunique()

        # 计算对比周期的产品总数（用于显示 Delta 增减）
        prev_product_count = compare_df['产品'].nunique() if not compare_df.empty else 0

        # 渲染到第六个卡片
        m6.metric(
            "在投产品数",
            f"{product_count} ",
            calc_delta(product_count, prev_product_count)
        )
        # --- 5. 图表可视化 ---
        st.markdown("---")
        left_chart, right_chart = st.columns([1, 1])

        with left_chart:
            st.subheader("📈 数据走势 (平台维度)")
            st.markdown("**选择趋势指标：**")
            target = st.selectbox("", ["收入", "成本", "利润", "ROI"], key="platform_trend_sel", label_visibility="collapsed")

            # --- 1. 数据预处理 ---

            trend_multi = filtered_df.groupby(['日期_dt', '平台']).agg({
                '收入': 'sum', '成本': 'sum', '利润': 'sum'
            }).reset_index()
            trend_multi['ROI'] = trend_multi.apply(lambda r: r['收入'] / r['成本'] if r['成本'] > 0 else 0, axis=1)

            trend_total = filtered_df.groupby('日期_dt').agg({
                '收入': 'sum', '成本': 'sum', '利润': 'sum'
            }).reset_index()
            trend_total['ROI'] = trend_total.apply(lambda r: r['收入'] / r['成本'] if r['成本'] > 0 else 0, axis=1)
            trend_total['平台'] = '📊 汇总合计'

            plot_df = pd.concat([trend_multi, trend_total])
            # 确保日期是时间格式，否则标签无法定位
            plot_df['日期_dt'] = pd.to_datetime(plot_df['日期_dt'])
            plot_df['显示收入'] = plot_df['收入'].apply(lambda x: f"{x:,.2f}")
            plot_df['显示ROI'] = plot_df['ROI'].apply(lambda x: f"{x:.2f}")
            plot_df['ROI_Status'] = plot_df['ROI'] < 1.2
            plot_df['Tooltip_收入'] = plot_df['收入'].apply(lambda x: f"¥{x:,.2f}")
            plot_df['Tooltip_ROI'] = plot_df['ROI'].apply(lambda x: f"{x:.2f}")
            # --- 【关键修复：提前在 Python 中计算末端点】 ---
            # 找到每条线（每个平台）日期最大的那一行，用于显示标签
            last_points = plot_df.sort_values('日期_dt').groupby('平台').last().reset_index()

            # --- 2. 交互式 Altair 绘图 (精准数值版) ---
            legend_selection = alt.selection_point(
                fields=['平台'],
                bind='legend',
                value=[{'平台': '📊 汇总合计'}]
            )

            platform_list = plot_df['平台'].unique().tolist()
            color_scale = alt.Scale(domain=platform_list, scheme='tableau20')

            # 基础图层
            base = alt.Chart(plot_df).encode(
                x=alt.X('日期_dt:T', title='日期', axis=alt.Axis(format='%m月%d日', labelAngle=-45, grid=False)),
                y=alt.Y(f'{target}:Q', title=target, axis=alt.Axis(grid=True, gridDash=[2, 2])),
                color=alt.Color('平台:N', scale=color_scale, legend=alt.Legend(title="图例 (点击切换显隐)")),
                opacity=alt.condition(legend_selection, alt.value(1), alt.value(0))
            ).add_params(legend_selection)

            # A. 线条层
            lines = base.mark_line().encode(
                strokeDash=alt.condition(alt.datum.平台 == '📊 汇总合计', alt.value([6, 4]), alt.value([0])),
                strokeWidth=alt.condition(alt.datum.平台 == '📊 汇总合计', alt.value(3), alt.value(2))
            )

            # B. 增强版数据点层
            points = base.mark_point(filled=True, size=60).encode(
                color=alt.condition(
                    alt.datum.ROI < 1.2,
                    alt.value("#EF4444"),
                    alt.Color('平台:N', scale=color_scale)
                ),
                tooltip=[
                    alt.Tooltip('日期_dt:T', title='日期', format='%m月%d日'),
                    alt.Tooltip('平台:N', title='平台'),
                    # 👈 使用预处理好的列，title 后面加一个空格有时能微调对齐感
                    alt.Tooltip('显示收入:N', title='收入 '),
                    alt.Tooltip('显示ROI:N', title='ROI  ')
                ]
            )

            # C. 末端标签层：标题下方留空已经在 configure_legend 里设置
            labels = alt.Chart(last_points).mark_text(
                align='left',
                dx=12,
                fontSize=12,
                fontWeight='bold'
            ).encode(
                x='日期_dt:T',
                y=f'{target}:Q',
                text='平台:N',
                color=alt.Color('平台:N', scale=color_scale, legend=None),
                opacity=alt.condition(legend_selection, alt.value(1), alt.value(0))
            )

            # 最终合并：包含 titlePadding 逻辑
            chart_combined = (lines + points + labels).properties(
                height=400,
                padding={'right': 150, 'top': 20}
            ).configure_legend(
                orient='right',
                offset=40,
                labelFontSize=12,
                symbolSize=100,
                rowPadding=10,
                titlePadding=20,  # 👈 图例标题下方的空行
                padding=20
            ).configure_view(
                strokeOpacity=0
            ).interactive()

            st.altair_chart(chart_combined, use_container_width=True)
            st.caption("💡 提示：点击右侧图例可显隐对应平台线，按住 Shift 可多选。")

            # --- 自动异常诊断逻辑 (修复版) ---
            st.markdown("---")

            # 1. 获取最近两天的日期
            recent_days = sorted(filtered_df['日期_dt'].unique(), reverse=True)

            if len(recent_days) >= 2:
                latest_day = recent_days[0]
                prev_day = recent_days[1]

                # 定义日期字符串用于标题
                latest_day_str = latest_day.strftime('%m/%d')
                prev_day_str = prev_day.strftime('%m/%d')
                st.markdown(f"🔍 **异常波动智能预警 ({prev_day_str} ➔ {latest_day_str})**")

                # 2. 分别计算这两天各产品的收入
                latest_data = filtered_df[filtered_df['日期_dt'] == latest_day].groupby('产品')['收入'].sum()
                prev_data = filtered_df[filtered_df['日期_dt'] == prev_day].groupby('产品')['收入'].sum()

                # 3. 计算差值并找出波动力度最大的产品
                diff = (latest_data - prev_data).dropna()

                if not diff.empty:
                    max_gain_prod = diff.idxmax()
                    max_gain_val = diff.max()
                    max_loss_prod = diff.idxmin()
                    max_loss_val = diff.min()

                    # 4. 渲染预警卡片
                    diag_col1, diag_col2 = st.columns(2)
                    with diag_col1:
                        if max_gain_val > 0:
                            st.success(f"📈 **增长最快**: {max_gain_prod}\n\n较前日增收: `+¥{max_gain_val:,.0f}`")
                    with diag_col2:
                        if max_loss_val < 0:
                            st.warning(f"📉 **跌幅最大**: {max_loss_prod}\n\n较前日减收: `-¥{abs(max_loss_val):,.0f}`")
                else:
                    st.info("💡 昨日数据波动平稳")
            else:
                st.markdown("🔍 **异常波动智能预警**")
                st.caption("ℹ️ 当前筛选范围内日期不足2天，无法进行跨日对比。")
            # --- 在数据走势图下方添加环比分析 ---
            st.markdown("---")
            st.markdown("📊 **核心指标环比分析**")

            if not compare_df.empty:
                # 1. 计算当前周期指标
                cur_inc = filtered_df['收入'].sum()
                cur_roi = filtered_df['收入'].sum() / filtered_df['成本'].sum() if filtered_df['成本'].sum() > 0 else 0
                cur_prof = filtered_df['利润'].sum()

                # 2. 计算上个周期指标
                prev_inc = compare_df['收入'].sum()
                prev_roi = compare_df['收入'].sum() / compare_df['成本'].sum() if compare_df['成本'].sum() > 0 else 0
                prev_prof = compare_df['利润'].sum()

                # 3. 渲染环比卡片 (使用 3 列布局)
                col_b1, col_b2, col_b3 = st.columns(3)

                with col_b1:
                    delta_inc = (cur_inc - prev_inc) / prev_inc if prev_inc > 0 else 0
                    st.metric("收入环比", f"{cur_inc / 10000:.1f}w", f"{delta_inc:.1%}")

                with col_b2:
                    delta_roi = cur_roi - prev_roi
                    st.metric("ROI变动", f"{cur_roi:.2f}", f"{delta_roi:.2f}", delta_color="normal")

                with col_b3:
                    delta_prof = (cur_prof - prev_prof) / prev_prof if prev_prof > 0 else 0
                    st.metric("利润环比", f"{cur_prof / 10000:.1f}w", f"{delta_prof:.1%}")

                st.caption("注：环比逻辑为当前选定日期区间 vs 上一个等长日期区间。")

            else:
                st.info("💡 请选择日期范围以查看环比分析")

            # --- 极致稳定版：低效产品警示 ---
            st.markdown(f"⚠️ **低效产品 Top 10 (按亏损额排序)**")

            # 1. 聚合计算
            loss_df = filtered_df.groupby('产品').agg({'收入': 'sum', '成本': 'sum'}).reset_index()
            loss_df['ROI'] = loss_df.apply(lambda r: r['收入'] / r['成本'] if r['成本'] > 0 else 0, axis=1)
            loss_df['亏损额'] = loss_df['成本'] - loss_df['收入']

            # 2. 筛选
            warning_list = loss_df[loss_df['ROI'] < 1.2].sort_values('亏损额', ascending=False).head(10)

            if not warning_list.empty:
                # 使用 container 包裹，防止布局塌陷
                with st.container():
                    # --- 在 warning_list 的循环中修改 ---
                    for _, row in warning_list.iterrows():
                        # 格式化亏损值
                        loss_val = f"{row['亏损额'] / 10000:.1f}w" if row['亏损额'] > 0 else "N/A"

                        # 使用 Markdown 的加粗语法 ** ** # 并使用 :red[...] 让亏损金额单独变红加粗（如果 st.error 背景太红看不清，也可以用 :orange）
                        st.error(
                            f"**{row['产品']}** \n"
                            f"💸 亏损额: **:red[{loss_val}]** | 📈 ROI: **{row['ROI']:.2f}** | 💰 收入: {row['收入'] / 10000:.1f}w"
                        )
            else:
                st.success("✅ 当前筛选下暂无低效产品")

        with right_chart:
            st.subheader("🏆 收入排行")
            # --- 修改点 2：加粗排行维度标题 ---
            st.markdown("**排行维度：**")
            rank_dim = st.radio("**排行维度：**", ["产品系列", "产品", "客户", "平台", "渠道类型"],
                                horizontal=True, label_visibility="collapsed")

            # 1. 数据聚合与排序
            rank_data = filtered_df.groupby(rank_dim).agg({'收入': 'sum', '成本': 'sum'}).reset_index()
            rank_data['ROI'] = rank_data.apply(lambda r: r['收入'] / r['成本'] if r['成本'] > 0 else 0, axis=1)
            rank_data = rank_data.sort_values('收入', ascending=False).head(10)
            sorted_order = rank_data[rank_dim].tolist()

            # 2. 基础图表定义
            base = alt.Chart(rank_data).encode(
                y=alt.Y(f'{rank_dim}:N', sort=sorted_order, title=None)
            )

            # 3. 柱状图层
            bars = base.mark_bar(color="#94A3B8").encode(
                x=alt.X('收入:Q',
                        title='总收入',
                        axis=alt.Axis(labelExpr="datum.value / 10000 + 'w'")),
                color=alt.Color('ROI:Q', scale=alt.Scale(scheme='blues'), title="ROI水平"),
                tooltip=[
                    alt.Tooltip(f'{rank_dim}:N', title=rank_dim),
                    alt.Tooltip('收入:Q', title='总收入', format=',.0f'),
                    alt.Tooltip('ROI:Q', title='对应ROI', format='.2f')
                ]
            )
            # 1. 定义文字颜色逻辑：ROI < 1.2 变红，否则保持深灰色/黑色
            text_color_condition = alt.condition(
                alt.datum.ROI < 1.2,
                alt.value("#EF4444"),  # 警示红
                alt.value("#475569")  # 正常的商务深灰
            )

            # 2. 修改文字层
            text = base.mark_text(
                align='left',
                baseline='middle',
                dx=5,
                fontWeight=600  # 加粗一点，让红色更醒目
            ).encode(
                x=alt.X('收入:Q'),
                text=alt.Text('label:N'),
                color=text_color_condition  # 应用颜色条件
            ).transform_calculate(
                label="round(datum.收入/10000) + 'w' + ' | ' + format(datum.ROI, '.2f')"
            )

            # 5. 合并渲染 —— 已修复：图例右移，不重叠
            chart_combined = (bars + text).properties(
                height=450
            ).configure_legend(
                orient='right',
                offset=100,  # 图例大幅右移，避免重叠
                padding=40,  # 内边距加大
                labelFontSize=12,
                symbolSize=100,
                titlePadding=20
            ).configure_view(
                strokeOpacity=0
            ).interactive()

            st.altair_chart(chart_combined, use_container_width=True)

            # --- 深度拆解分析区 ---
            st.markdown("---")
            st.markdown("🔍 **深度拆解分析**")

            # 获取当前排行中的选项（前10名）
            drill_options = rank_data[rank_dim].tolist()
            selected_item = st.selectbox(f"选择要拆解的【{rank_dim}】：", ["-- 查看全部 --"] + drill_options)

            if selected_item != "-- 查看全部 --":
                # 1. 过滤数据并按产品聚合
                drill_df = filtered_df[filtered_df[rank_dim] == selected_item]
                prod_data = drill_df.groupby('产品').agg({'收入': 'sum', '成本': 'sum'}).reset_index()
                prod_data['ROI'] = prod_data.apply(lambda r: r['收入'] / r['成本'] if r['成本'] > 0 else 0, axis=1)

                # 【关键】：排序并取前 10
                prod_data = prod_data.sort_values('收入', ascending=False).head(10)
                # 获取产品排序名单，强制固定图表顺序
                drill_sorted_order = prod_data['产品'].tolist()

                # 2. 绘制下钻拆解图
                drill_base = alt.Chart(prod_data).encode(
                    # 使用固定的名单顺序进行排序
                    y=alt.Y('产品:N', sort=drill_sorted_order, title=None)
                )

                drill_bars = drill_base.mark_bar(color="#1E40AF", opacity=0.8).encode(
                    x=alt.X('收入:Q', title=None, axis=None),
                    color=alt.Color('ROI:Q', scale=alt.Scale(scheme='blues'), legend=None),
                    tooltip=[
                        alt.Tooltip('产品:N'),
                        alt.Tooltip('收入:Q', title='收入', format=',.0f'),
                        alt.Tooltip('ROI:Q', title='ROI', format='.2f')
                    ]
                )

                # 在下钻分析的 drill_text 中修改
                drill_text_color = alt.condition(
                    alt.datum.ROI < 1.2,
                    alt.value("#EF4444"),
                    alt.value("#475569")
                )

                drill_text = drill_base.mark_text(
                    align='left',
                    baseline='middle',
                    dx=5,
                    fontSize=11,
                    fontWeight=600
                ).encode(
                    x=alt.X('收入:Q'),
                    text=alt.Text('label:N'),
                    color=drill_text_color  # 应用颜色条件
                ).transform_calculate(
                    label="round(datum.收入/10000) + 'w' + ' | ' + format(datum.ROI, '.2f')"
                )

                st.caption(f"💡 【{selected_item}】内部产品贡献排行 (Top 10)：")
                # 增加高度到 350，以容纳 10 根柱子而不显得拥挤
                drill_chart = (drill_bars + drill_text).properties(
                    height=350
                ).configure_legend(
                    offset=100, padding=40
                ).configure_view(strokeOpacity=0)

                st.altair_chart(drill_chart, use_container_width=True)
        # ============================================================
        # --- 6. 数据明细列表 (核心修改：确保这里左边没有任何多余缩进) ---
        # ============================================================
        st.markdown("---")
        st.subheader("📋 数据明细列表 (仅展示前1000条)")

        # 准备展示数据
        display_df = filtered_df.copy().head(1000)
        if '日期_dt' in display_df.columns:
            display_df['日期'] = display_df['日期_dt'].apply(lambda x: x.strftime('%Y-%m-%d'))


        # 定义染色函数
        def highlight_row(row):
            style = 'color: #EF4444; font-weight: bold;' if not row['是否达标'] else ''
            return [style] * len(row)


        # 渲染表格 - 现在的层级在 columns 之外，所以会 100% 平铺
        st.dataframe(
            display_df.style.apply(highlight_row, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "是否达标": None,
                "日期_dt": None,
                "ROI": st.column_config.NumberColumn("ROI", format="%.2f"),
                "收入": st.column_config.NumberColumn("收入", format="¥%d"),
                "成本": st.column_config.NumberColumn("成本", format="¥%d")
            }
        )
else:
    # 未上传文件时的提示
    st.info("👈 请在左侧侧边栏上传 Excel 数据文件（仅支持 .xlsx / .xls）")
