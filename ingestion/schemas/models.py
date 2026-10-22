"""Pydantic models that gate raw records. Only key fields are required; unknown fields pass through."""
from pydantic import BaseModel, ConfigDict, ValidationError


class _Raw(BaseModel):
    model_config = ConfigDict(extra="allow")


class Shortage(_Raw):
    generic_name: str
    company_name: str
    status: str
    initial_posting_date: str
    package_ndc: str


class Recall(_Raw):
    recall_number: str
    classification: str
    status: str
    recalling_firm: str
    report_date: str
    product_description: str


class NdcProduct(_Raw):
    product_ndc: str
    generic_name: str
    labeler_name: str
    dosage_form: str


def validate(records: list[dict], model: type[BaseModel]) -> tuple[list[dict], list[dict]]:
    """Split records into (valid, quarantined). Quarantined rows carry the validation error."""
    good, bad = [], []
    for r in records:
        try:
            model.model_validate(r)
            good.append(r)
        except ValidationError as e:
            bad.append({"record": r, "error": e.errors(include_url=False, include_input=False)})
    return good, bad


class WarningLetter(_Raw):
    posted_date: str
    letter_issue_date: str
    company_name: str
    issuing_office: str
