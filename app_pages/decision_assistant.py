"""Hospital-first decision assistant with lookup only for missing parameters."""

from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from src.decision_assistant.parameter_plan import LOOKUP_ROUTES, build_parameter_plan
from src.library import CareGapLibraryRepository
from src.models import (
    MODEL_SCOPE_ZH,
    SUPPORTED_SCREENING_MODALITY,
    BreastROIInputs,
    calculate_breast_roi,
)
from src.reporting import (
    ReportAudience, build_demo_report, generate_report_with_openai,
    validate_executive_report,
)


DATA_DIR = Path(__file__).parents[1] / "data"
SOURCE_LINKS = {
    "SEER": "https://seer.cancer.gov/statistics-network/explorer/",
    "CMS": "https://www.cms.gov/medicare/payment/fee-schedules",
    "USPSTF": "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/breast-cancer-screening",
    "PubMed": "https://pubmed.ncbi.nlm.nih.gov/",
}


def safe_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def approved_evidence() -> list[dict[str, str]]:
    repo = CareGapLibraryRepository(DATA_DIR / "care_gap_value_library.csv", DATA_DIR / "care_gap_audit.jsonl")
    return [row for row in repo.list_records() if row.get("review_status") == "Approved"]


st.caption("先使用医院数据；只有缺失参数才查外部依据。AI不计算ROI，也不会自动改参数。")
st.info(MODEL_SCOPE_ZH, icon=":material/verified:")
st.info(
    "正确顺序：医院材料 → 缺失项检查 → 按参数补充来源 → 人工确认 → 原R公式计算 → 报告。",
    icon=":material/route:",
)

for key, default in {
    "assistant_scenario": None, "assistant_result": None, "assistant_report": None,
    "assistant_parameter_sources": {},
}.items():
    st.session_state.setdefault(key, default)

st.subheader("1. 提供医院情况")
approved_population = st.session_state.get("approved_population")
metadata = st.session_state.get("approved_population_metadata")
if approved_population is None:
    # A clean start must never display or reuse the historical demo scenario.
    for key in (
        "assistant_scenario", "assistant_result", "assistant_report",
        "assistant_parameter_sources", "assistant_detection_value",
        "assistant_recall_value", "assistant_dataset_signature",
    ):
        st.session_state.pop(key, None)
    st.warning("当前没有医院数据。请先从顶部进入“数据接入”，上传并应用 CSV 数据集。")
    st.info("上传后回到本页，系统会自动读取人群规模、平均年龄和当前筛查率。这里不会显示或使用任何演示医院数据。")
    st.stop()

dataset_signature = None
dataset_signature = f"{metadata.get('source_name', '')}:{len(approved_population)}"
if st.session_state.get("assistant_dataset_signature") != dataset_signature:
    # Never allow an old manual/demo scenario to survive a dataset change.
    st.session_state.assistant_scenario = None
    st.session_state.assistant_result = None
    st.session_state.assistant_report = None
    st.session_state.assistant_parameter_sources = {}
    st.session_state.assistant_dataset_signature = dataset_signature
    for widget_key in ("assistant_detection_value", "assistant_recall_value"):
        st.session_state.pop(widget_key, None)

st.success(
    f"已读取当前会话医院数据：{metadata.get('source_name', '已批准数据集')}，"
    f"{len(approved_population):,} 行。",
    icon=":material/database:",
)

if st.session_state.assistant_scenario is None:
    st.write("医院数据已经提供了人群规模、年龄和当前筛查情况。请只补充数据集中没有的目标筛查率：")
    with st.form("dataset_scenario_setup", border=True):
        target_from_hospital = st.number_input("目标筛查率（%）", 0.0, 100.0, 70.0, step=1.0)
        st.markdown(f"**筛查方式：** {SUPPORTED_SCREENING_MODALITY}（当前版本固定）")
        setup_dataset = st.form_submit_button("使用医院数据建立分析场景", type="primary", icon=":material/arrow_forward:")
    if setup_dataset:
        st.session_state.assistant_scenario = {
            "population_size": None,
            "current_screening_rate": None,
            "target_screening_rate": float(target_from_hospital),
            "average_age": None,
            "screening_modality": SUPPORTED_SCREENING_MODALITY,
            "cancer_detection_per_1000": None,
            "recall_rate": None,
            "missing_fields": ["cancer_detection_per_1000", "recall_rate"],
            "assumptions": ["人群规模、平均年龄和当前筛查率由已批准医院数据集推导。"],
            "pubmed_query": "DBT breast screening cancer detection recall meta-analysis",
        }
        st.rerun()

if st.session_state.assistant_scenario is None:
    st.stop()

draft = st.session_state.assistant_scenario
plan = build_parameter_plan(draft, approved_population)

st.subheader("2. 系统检查已知与缺失参数")
rows = []
for item in plan:
    rows.append({
        "参数": item.label,
        "当前值": "待补充" if item.value is None else str(item.value),
        "来源类型": item.source_type,
        "来源说明": item.source_detail,
        "缺失时去哪里找": item.lookup_route or "—",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

missing = [item for item in plan if item.value is None]
if not missing:
    st.success("运行ROI所需的基础参数已齐全。你可以直接进入确认步骤。", icon=":material/check_circle:")
else:
    st.warning(f"发现 {len(missing)} 个缺失参数。只需要处理这些项目，不必先搜索一批随机文献。")

st.subheader("3. 只补充缺失参数")
defaults = BreastROIInputs()
source_records = st.session_state.assistant_parameter_sources
for item in missing:
    with st.container(border=True):
        st.markdown(f"**{item.label}**")
        st.write(f"建议来源：{item.lookup_route}")
        if item.key == "cancer_detection_per_1000":
            st.link_button("打开PubMed定向检索", SOURCE_LINKS["PubMed"] + "?term=%28digital+breast+tomosynthesis+OR+DBT%29+AND+breast+screening+AND+cancer+detection+rate+AND+meta-analysis", icon=":material/open_in_new:")
            default_value = defaults.cancer_detection_per_1000
        else:
            st.link_button("打开PubMed定向检索", SOURCE_LINKS["PubMed"] + "?term=%28digital+breast+tomosynthesis+OR+DBT%29+AND+breast+screening+AND+recall+rate+AND+meta-analysis", icon=":material/open_in_new:")
            default_value = defaults.recall_rate
        with st.form(f"missing_{item.key}", border=False):
            value = st.number_input("填写候选值", min_value=0.0, value=float(default_value), step=0.1)
            source_kind = st.selectbox("来源", ["R模型默认值", "医院数据", "PubMed文献", "其他官方来源", "情景假设"])
            source_detail = st.text_input("来源说明", placeholder="例如：PMID、医院报表名称、SEER年份或假设理由")
            save = st.form_submit_button("保存该参数及来源", type="primary", icon=":material/save:")
        if save:
            source_records[item.key] = {"value": float(value), "source": source_kind, "detail": source_detail or "未补充详细说明"}
            st.session_state.assistant_parameter_sources = source_records
            st.rerun()
        if item.key in source_records:
            saved = source_records[item.key]
            st.success(f"已保存：{saved['value']:g}；来源：{saved['source']}；{saved['detail']}")

with st.expander("其他模型参数来自哪里？", icon=":material/source:"):
    st.write("发病率和分期分布优先使用SEER；成本优先使用医院财务数据，缺失时参考CMS；筛查年龄与频率参考官方指南；Stage shift证据不足时应作为敏感性假设。")
    with st.container(horizontal=True):
        for label in ("SEER", "CMS", "USPSTF", "PubMed"):
            st.link_button(label, SOURCE_LINKS[label], icon=":material/open_in_new:")

st.subheader("4. 人工确认并运行原R模型公式")
plan_map = {item.key: item.value for item in plan}
detection_record = source_records.get("cancer_detection_per_1000")
recall_record = source_records.get("recall_rate")
st.session_state.setdefault("assistant_detection_value", float(detection_record["value"] if detection_record else defaults.cancer_detection_per_1000))
st.session_state.setdefault("assistant_recall_value", float(recall_record["value"] if recall_record else defaults.recall_rate))

with st.form("hospital_first_confirmation", border=True):
    population = st.number_input("目标人群规模", min_value=1_000, value=int(plan_map["population_size"]), step=1_000)
    current_rate = st.number_input("当前筛查率（%）", 0.0, 100.0, float(plan_map["current_screening_rate"]))
    target_rate = st.number_input("目标筛查率（%）", 0.0, 100.0, float(plan_map["target_screening_rate"]))
    average_age = st.number_input("平均年龄", 40, 74, int(plan_map["average_age"]))
    st.markdown(f"**筛查方式：** {SUPPORTED_SCREENING_MODALITY}（当前版本固定）")
    detection = st.number_input("癌症检出率（每千次筛查）", min_value=0.0, step=0.1, key="assistant_detection_value")
    recall = st.number_input("召回率（%）", 0.0, 100.0, step=0.1, key="assistant_recall_value")
    acknowledge = st.checkbox("我已检查参数值及来源；缺乏证据的数值已明确标记为默认值或情景假设。")
    confirmed = st.form_submit_button("确认并运行ROI", type="primary", icon=":material/calculate:")

if confirmed:
    if not acknowledge:
        st.error("请先确认参数来源。")
    else:
        inputs = BreastROIInputs(**{
            **asdict(defaults), "population_size": int(population),
            "current_screening_rate": float(current_rate), "target_screening_rate": float(target_rate),
            "average_age": int(average_age), "screening_modality": SUPPORTED_SCREENING_MODALITY,
            "cancer_detection_per_1000": float(detection), "recall_rate": float(recall),
        })
        result = calculate_breast_roi(inputs)
        st.session_state.roi_inputs_snapshot = asdict(inputs)
        st.session_state.assistant_roi_inputs_snapshot = asdict(inputs)
        st.session_state.roi_results_snapshot = asdict(result)
        st.session_state.assistant_result = asdict(result)
        st.session_state.assistant_report = None

if st.session_state.assistant_result:
    result = st.session_state.assistant_result
    st.subheader("5. ROI结果")
    with st.container(horizontal=True):
        st.metric("新增筛查", f"{result['additional_screened']:,.0f}", border=True)
        st.metric("预计检出病例", f"{result['detected_breast_cancer_cases']:.1f}", border=True)
        st.metric("模型净节约", f"${result['net_savings']:,.0f}", border=True)
        st.metric("模型ROI", "N/A" if result["roi"] is None else f"{result['roi']:.1%}", border=True)
    with st.expander("查看计算过程", icon=":material/functions:"):
        st.caption("以下结果来自确定性ROI模型，不是大模型计算结果。")
        st.dataframe(pd.DataFrame({"指标": result.keys(), "数值": [str(v) for v in result.values()]}), hide_index=True, width="stretch")

    st.subheader("6. 生成管理层报告")
    live_report = st.checkbox("使用AI撰写报告", value=True)
    if st.button("生成报告", type="primary", icon=":material/description:"):
        evidence = approved_evidence()
        try:
            if live_report:
                report = generate_report_with_openai(
                    "Executive", st.session_state.roi_inputs_snapshot, result, evidence,
                    safe_secret("OPENAI_API_KEY"), safe_secret("OPENAI_MODEL", "gpt-5.6-luna"), "Chinese",
                )
            else:
                report = build_demo_report(ReportAudience.EXECUTIVE, result, evidence, "Chinese")
            st.session_state.assistant_report = validate_executive_report(
                report, result, evidence, st.session_state.roi_inputs_snapshot
            ).model_dump(mode="json")
        except Exception as exc:
            st.error(f"报告生成或校验失败：{exc}")

if st.session_state.assistant_report:
    report = st.session_state.assistant_report

    def display_report_text(value: str) -> None:
        """Render report prose without treating currency signs as LaTeX."""
        st.markdown(str(value).replace("$", r"\$"))

    with st.container(border=True):
        st.subheader("管理层报告草稿")
        for label, key in (("管理层摘要", "executive_summary"), ("临床影响", "clinical_impact"), ("财务影响", "financial_impact"), ("证据解读", "evidence_interpretation")):
            st.markdown(f"**{label}**")
            display_report_text(report[key])
        st.markdown("**关键假设**")
        for item in report["key_assumptions"]:
            display_report_text(f"- {item}")
        st.markdown("**局限性**")
        for item in report["limitations"]:
            display_report_text(f"- {item}")
        st.markdown("**建议的下一步行动**")
        for item in report["recommended_actions"]:
            display_report_text(f"- {item}")
