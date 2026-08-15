"""Entry point and navigation for Breast ROI Copilot."""

import streamlit as st

from src.i18n import t

st.set_page_config(
    page_title="乳腺筛查循证 ROI 智能决策平台",
    page_icon=":material/health_metrics:",
    layout="wide",
)

st.session_state.setdefault("app_language", "中文")
st.sidebar.segmented_control(
    "语言 / Language",
    ["中文", "English"],
    key="app_language",
)

page = st.navigation(
    {
        "": [
            st.Page(
                "app_pages/decision_assistant.py",
                title="AI 决策助手",
                icon=":material/assistant:",
                default=True,
            ),
        ],
        "数据接入": [
            st.Page("app_pages/data_intake.py", title="上传与检查", icon=":material/upload_file:"),
        ],
        "证据与参数": [
            st.Page("app_pages/evidence_value_library.py", title="证据与参数", icon=":material/library_books:"),
        ],
        "决策分析": [
            st.Page("app_pages/roi_simulation.py", title="高级 ROI 仿真", icon=":material/analytics:"),
            st.Page("app_pages/risk_prioritization.py", title="外展资源优化", icon=":material/social_leaderboard:"),
        ],
    },
    position="top",
)

st.caption(t("APEX · BREAST SCREENING DECISION INTELLIGENCE"))
st.title(f"{page.icon} {page.title}")
page.run()
