"""Deterministic, clearly labeled report demo requiring no LLM call."""

from .schemas import EvidenceClaim, ExecutiveReport, ReportAudience


def build_demo_report(
    audience: ReportAudience,
    roi_output: dict,
    approved_evidence: list[dict[str, str]],
    output_language: str = "English",
) -> ExecutiveReport:
    zh = output_language.casefold() in {"chinese", "中文", "zh"}
    roi = roi_output.get("roi")
    roi_text = "not available" if roi is None else f"{float(roi):.1%}"
    evidence_claims: list[EvidenceClaim] = []
    cited_pmids: list[str] = []
    interpretation = "证据不足。" if zh else "Insufficient evidence."
    if approved_evidence:
        row = approved_evidence[0]
        pmid = str(row.get("pmid", ""))
        excerpt = str(row.get("evidence_excerpt", "")).strip()
        if pmid and excerpt:
            evidence_claims = [
                EvidenceClaim(
                    claim=str(row.get("outcome") or "The approved record is relevant to the screening decision."),
                    pmids=[pmid],
                    evidence_excerpt=excerpt,
                )
            ]
            cited_pmids = [pmid]
            interpretation = (
                f"当前有一条经人工批准的证据记录（PMID {pmid}）；其适用性仍受研究人群与既有研究局限约束。"
                if zh else
                f"One human-approved evidence record is available (PMID {pmid}); its applicability remains subject to the documented population and study limitations."
            )

    if zh:
        return ExecutiveReport(
            audience=audience,
            executive_summary=(
                f"确定性场景预计新增筛查 {roi_output['additional_screened']:,.0f} 人，模型 ROI 为 {roi_text}。"
                "以上均为模型输出，不代表对实际结果的保证。"
            ),
            clinical_impact=(
                f"在既定假设下，模型预计检出乳腺癌病例 {roi_output['detected_breast_cancer_cases']:.1f} 例，"
                f"挽救生命 {roi_output['lives_saved']:.1f} 人。"
            ),
            financial_impact=(
                f"模型项目成本为 ${roi_output['screening_program_cost']:,.0f}，净节约为 "
                f"${roi_output['net_savings']:,.0f}。这些数值为确定性模型预测结果。"
            ),
            evidence_interpretation=interpretation,
            key_assumptions=[
                "检出率、死亡率、分期分布、分期转移和成本均属于模型假设。",
                "参数助手建议只有经过人工确认后才能进入模型。",
            ],
            limitations=[
                "本工具为场景模型，不能证明实际临床或财务结果。",
                "仅基于摘要的证据可能无法提供可直接迁移的效应量。",
            ],
            recommended_actions=[
                "与临床、财务和支付方相关人员共同审核全部假设。",
                "在将场景用于规划前进行敏感性分析。",
            ],
            evidence_claims=evidence_claims,
            cited_pmids=cited_pmids,
            simulation_snapshot=dict(roi_output),
        )

    return ExecutiveReport(
        audience=audience,
        executive_summary=(
            f"The deterministic scenario estimates {roi_output['additional_screened']:,.0f} "
            f"additional screens and an ROI of {roi_text}. These are modeled outputs, not guaranteed outcomes."
        ),
        clinical_impact=(
            f"The model estimates {roi_output['detected_breast_cancer_cases']:.1f} detected cases "
            f"and {roi_output['lives_saved']:.1f} lives saved under its stated assumptions."
        ),
        financial_impact=(
            f"Modeled program cost is ${roi_output['screening_program_cost']:,.0f}, with net savings "
            f"of ${roi_output['net_savings']:,.0f}. These values are projections from the deterministic model."
        ),
        evidence_interpretation=interpretation,
        key_assumptions=[
            "Detection, mortality, stage distribution, stage-shift, and cost inputs are model assumptions.",
            "Parameter Copilot values enter the model only after human confirmation.",
        ],
        limitations=[
            "This is a scenario model and does not establish realized clinical or financial outcomes.",
            "Abstract-level evidence may not provide directly transferable effect sizes.",
        ],
        recommended_actions=[
            "Review all assumptions with clinical, finance, and payer stakeholders.",
            "Run sensitivity analyses before using the scenario for planning.",
        ],
        evidence_claims=evidence_claims,
        cited_pmids=cited_pmids,
        simulation_snapshot=dict(roi_output),
    )
