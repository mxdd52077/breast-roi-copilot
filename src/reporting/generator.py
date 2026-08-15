"""Optional OpenAI provider for a structured executive report."""

from .prompts import SYSTEM_PROMPT, build_report_prompt
from .schemas import ExecutiveReport
from .validator import ReportValidationError, validate_executive_report


class ReportGenerationError(RuntimeError):
    """A safe failure from the live report provider."""


def generate_report_with_openai(
    audience: str,
    roi_inputs: dict,
    roi_output: dict,
    approved_evidence: list[dict[str, str]],
    api_key: str,
    model: str = "gpt-5.6-luna",
    output_language: str = "English",
) -> ExecutiveReport:
    if not api_key.strip():
        raise ValueError("An OpenAI API key is required for live report generation.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ReportGenerationError(
            "The OpenAI SDK is not installed. Run pip install -r requirements.txt."
        ) from exc

    try:
        client = OpenAI(api_key=api_key)
        request_input = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_report_prompt(
                    audience, roi_inputs, roi_output, approved_evidence, output_language
                ),
            },
        ]
        last_validation_error: ReportValidationError | None = None

        # A model can occasionally mistype a supplied number even with structured output.
        # Retry once with the deterministic validator's exact failure reason; never show
        # either draft unless it passes the same checks used by the UI.
        for attempt in range(2):
            response = client.responses.parse(
                model=model,
                input=request_input,
                text_format=ExecutiveReport,
            )
            if response.output_parsed is None:
                raise ReportGenerationError("The model did not return a structured report.")
            try:
                return validate_executive_report(
                    response.output_parsed,
                    roi_output,
                    approved_evidence,
                    roi_inputs,
                )
            except ReportValidationError as exc:
                last_validation_error = exc
                if attempt == 0:
                    request_input.append(
                        {
                            "role": "user",
                            "content": (
                                "The previous draft failed deterministic validation: "
                                f"{exc} Regenerate the complete report. Copy narrative "
                                "numbers only from ROI_INPUTS or ROI_OUTPUT, using only the "
                                "permitted display rounding. Do not estimate, recompute, or "
                                "introduce any additional number."
                            ),
                        }
                    )

        raise ReportGenerationError(
            "The AI draft failed deterministic numeric or citation validation after one "
            f"automatic correction attempt: {last_validation_error}"
        )
    except ReportGenerationError:
        raise
    except Exception as exc:
        raise ReportGenerationError(
            "Live report generation failed. No unvalidated report was displayed."
        ) from exc
