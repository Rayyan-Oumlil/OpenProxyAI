"""Vertical-specific compliance templates for policy engine auto-configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


@dataclass(frozen=True)
class TemplateMetadata:
	template: str
	template_version: int
	audit_retention_days: int


@dataclass(frozen=True)
class TemplateDef:
	"""Compliance template definition — policy fields + metadata."""

	enforcement_mode: str
	blocked_keywords: list[str]
	pii_detection_enabled: bool
	pii_entities: list[str]
	prompt_injection_detection_enabled: bool
	response_guardrails_enabled: bool
	response_pii_redact: bool
	allowed_models: list[str] = field(default_factory=list)
	model_rate_limits: dict = field(default_factory=dict)
	metadata: TemplateMetadata = field(default_factory=lambda: TemplateMetadata("", 1, 0))


HEALTHCARE_HIPAA = TemplateDef(
	enforcement_mode="enforce",
	blocked_keywords=[
		"diagnosis",
		"patient name",
		"medical record",
		"prescription",
		"treatment plan",
	],
	pii_detection_enabled=True,
	pii_entities=[
		"PERSON",
		"PHONE_NUMBER",
		"EMAIL_ADDRESS",
		"US_SSN",
		"CREDIT_CARD",
		"DATE_OF_BIRTH",
		"MEDICAL_LICENSE",
		"US_DRIVER_LICENSE",
	],
	prompt_injection_detection_enabled=True,
	response_guardrails_enabled=True,
	response_pii_redact=True,
	allowed_models=[],
	model_rate_limits={},
	metadata=TemplateMetadata(
		template="healthcare_hipaa",
		template_version=1,
		audit_retention_days=2555,  # 7 years HIPAA requirement
	),
)

FINANCE_PCI = TemplateDef(
	enforcement_mode="enforce",
	blocked_keywords=[
		"account number",
		"routing number",
		"wire transfer",
		"swift code",
		"trading strategy",
		"insider",
	],
	pii_detection_enabled=True,
	pii_entities=[
		"PERSON",
		"CREDIT_CARD",
		"US_BANK_NUMBER",
		"US_SSN",
		"IBAN_CODE",
		"PHONE_NUMBER",
		"EMAIL_ADDRESS",
	],
	prompt_injection_detection_enabled=True,
	response_guardrails_enabled=True,
	response_pii_redact=True,
	allowed_models=[],
	model_rate_limits={},
	metadata=TemplateMetadata(
		template="finance_pci",
		template_version=1,
		audit_retention_days=365,
	),
)

GOVERNMENT_FEDRAMP = TemplateDef(
	enforcement_mode="enforce",
	blocked_keywords=[
		"classified",
		"top secret",
		"secret//noforn",
		"controlled unclassified",
		"fouo",
	],
	pii_detection_enabled=True,
	pii_entities=[
		"PERSON",
		"PHONE_NUMBER",
		"EMAIL_ADDRESS",
		"US_SSN",
		"US_PASSPORT",
		"US_DRIVER_LICENSE",
		"CREDIT_CARD",
		"IP_ADDRESS",
		"LOCATION",
	],
	prompt_injection_detection_enabled=True,
	response_guardrails_enabled=True,
	response_pii_redact=True,
	allowed_models=[],
	model_rate_limits={},
	metadata=TemplateMetadata(
		template="government_fedramp",
		template_version=1,
		audit_retention_days=1095,  # 3 years
	),
)

TEMPLATES: dict[str, TemplateDef] = {
	"healthcare_hipaa": HEALTHCARE_HIPAA,
	"finance_pci": FINANCE_PCI,
	"government_fedramp": GOVERNMENT_FEDRAMP,
}


class TemplateListItem(TypedDict):
	name: str
	description: str
	configures: list[str]


_TEMPLATE_LIST: list[TemplateListItem] = [
	{
		"name": "healthcare_hipaa",
		"description": "HIPAA-aligned guardrails for healthcare: PHI protection, PII redaction, 7-year audit retention.",
		"configures": [
			"Enforcement mode: enforce",
			"Blocked keywords: diagnosis, patient name, medical record, prescription, treatment plan",
			"PII detection + redaction enabled",
			"Prompt injection detection",
			"Response guardrails with PII redaction",
			"Audit retention: 7 years (HIPAA)",
		],
	},
	{
		"name": "finance_pci",
		"description": "PCI-DSS-aligned guardrails for financial services: payment data protection, insider trading keywords.",
		"configures": [
			"Enforcement mode: enforce",
			"Blocked keywords: account number, routing number, wire transfer, swift code, trading strategy, insider",
			"PII detection + redaction enabled",
			"Prompt injection detection",
			"Response guardrails with PII redaction",
			"Audit retention: 1 year",
		],
	},
	{
		"name": "government_fedramp",
		"description": "FedRAMP-aligned guardrails for government: classification keywords, US-only provider recommendations.",
		"configures": [
			"Enforcement mode: enforce",
			"Blocked keywords: classified, top secret, secret//noforn, controlled unclassified, fouo",
			"PII detection + redaction enabled",
			"Prompt injection detection",
			"Response guardrails with PII redaction",
			"Audit retention: 3 years",
		],
	},
]


def get_template(name: str) -> TemplateDef | None:
	return TEMPLATES.get(name)


def list_templates() -> list[TemplateListItem]:
	return list(_TEMPLATE_LIST)
