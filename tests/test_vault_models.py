# tests/test_vault_models.py
"""Tests for vault models including Framework enums and dataclasses."""

import pytest

from scimesh.vault.models import (
    FieldCategory,
    FieldSchema,
    Framework,
    FrameworkType,
    Protocol,
)


class TestFrameworkTypeEnum:
    """Tests for FrameworkType enum."""

    def test_pico_value(self):
        assert FrameworkType.PICO.value == "pico"

    def test_spider_value(self):
        assert FrameworkType.SPIDER.value == "spider"

    def test_custom_value(self):
        assert FrameworkType.CUSTOM.value == "custom"

    def test_all_values_exist(self):
        values = {ft.value for ft in FrameworkType}
        assert values == {"pico", "spider", "custom"}


class TestFieldCategoryEnum:
    """Tests for FieldCategory enum."""

    def test_context_value(self):
        assert FieldCategory.CONTEXT.value == "context"

    def test_action_value(self):
        assert FieldCategory.ACTION.value == "action"

    def test_comparison_value(self):
        assert FieldCategory.COMPARISON.value == "comparison"

    def test_result_value(self):
        assert FieldCategory.RESULT.value == "result"

    def test_all_values_exist(self):
        values = {fc.value for fc in FieldCategory}
        assert values == {"context", "action", "comparison", "result"}


class TestFieldSchema:
    """Tests for FieldSchema dataclass."""

    def test_creation_minimal(self):
        schema = FieldSchema(name="population", category=FieldCategory.CONTEXT)
        assert schema.name == "population"
        assert schema.category == FieldCategory.CONTEXT
        assert schema.required is True
        assert schema.description == ""

    def test_creation_full(self):
        schema = FieldSchema(
            name="intervention",
            category=FieldCategory.ACTION,
            required=False,
            description="The intervention being studied",
        )
        assert schema.name == "intervention"
        assert schema.category == FieldCategory.ACTION
        assert schema.required is False
        assert schema.description == "The intervention being studied"

    def test_frozen(self):
        schema = FieldSchema(name="test", category=FieldCategory.CONTEXT)
        with pytest.raises(AttributeError):
            schema.name = "changed"

    def test_to_dict(self):
        schema = FieldSchema(
            name="outcome",
            category=FieldCategory.RESULT,
            required=True,
            description="Expected outcome",
        )
        result = schema.to_dict()
        assert result == {
            "name": "outcome",
            "category": "result",
            "required": True,
            "description": "Expected outcome",
        }

    def test_to_dict_minimal(self):
        schema = FieldSchema(name="test", category=FieldCategory.ACTION)
        result = schema.to_dict()
        assert result == {
            "name": "test",
            "category": "action",
            "required": True,
            "description": "",
        }

    def test_from_dict(self):
        data = {
            "name": "population",
            "category": "context",
            "required": False,
            "description": "Target population",
        }
        schema = FieldSchema.from_dict(data)
        assert schema.name == "population"
        assert schema.category == FieldCategory.CONTEXT
        assert schema.required is False
        assert schema.description == "Target population"

    def test_from_dict_minimal(self):
        data = {"name": "test", "category": "action"}
        schema = FieldSchema.from_dict(data)
        assert schema.name == "test"
        assert schema.category == FieldCategory.ACTION
        assert schema.required is True
        assert schema.description == ""

    def test_roundtrip(self):
        original = FieldSchema(
            name="sample",
            category=FieldCategory.COMPARISON,
            required=False,
            description="Sample field",
        )
        restored = FieldSchema.from_dict(original.to_dict())
        assert restored == original


class TestFramework:
    """Tests for Framework dataclass."""

    def test_creation_pico(self):
        framework = Framework(
            type=FrameworkType.PICO,
            fields={
                "population": "elderly patients",
                "intervention": "exercise",
                "comparison": "no exercise",
                "outcome": "mortality",
            },
        )
        assert framework.type == FrameworkType.PICO
        assert framework.fields["population"] == "elderly patients"
        assert framework.schema == ()

    def test_creation_spider(self):
        framework = Framework(
            type=FrameworkType.SPIDER,
            fields={
                "sample": "healthcare workers",
                "phenomenon": "burnout",
                "design": "qualitative interviews",
                "evaluation": "thematic analysis",
                "research_type": "qualitative",
            },
        )
        assert framework.type == FrameworkType.SPIDER
        assert framework.fields["sample"] == "healthcare workers"

    def test_creation_custom_with_schema(self):
        custom_schema = (
            FieldSchema(name="context", category=FieldCategory.CONTEXT),
            FieldSchema(name="mechanism", category=FieldCategory.ACTION),
            FieldSchema(name="outcome", category=FieldCategory.RESULT),
        )
        framework = Framework(
            type=FrameworkType.CUSTOM,
            fields={"context": "test", "mechanism": "test", "outcome": "test"},
            schema=custom_schema,
        )
        assert framework.type == FrameworkType.CUSTOM
        assert len(framework.schema) == 3
        assert framework.schema[0].name == "context"

    def test_frozen(self):
        framework = Framework(type=FrameworkType.PICO, fields={"population": "test"})
        with pytest.raises(AttributeError):
            framework.type = FrameworkType.SPIDER

    def test_to_dict_pico(self):
        framework = Framework(
            type=FrameworkType.PICO,
            fields={
                "population": "patients",
                "intervention": "drug",
                "comparison": "placebo",
                "outcome": "recovery",
            },
        )
        result = framework.to_dict()
        assert result == {
            "type": "pico",
            "fields": {
                "population": "patients",
                "intervention": "drug",
                "comparison": "placebo",
                "outcome": "recovery",
            },
        }
        # Schema should not be included when empty
        assert "schema" not in result

    def test_to_dict_custom_with_schema(self):
        custom_schema = (
            FieldSchema(
                name="context",
                category=FieldCategory.CONTEXT,
                description="The context",
            ),
        )
        framework = Framework(
            type=FrameworkType.CUSTOM,
            fields={"context": "my context"},
            schema=custom_schema,
        )
        result = framework.to_dict()
        assert result["type"] == "custom"
        assert result["fields"] == {"context": "my context"}
        assert "schema" in result
        assert len(result["schema"]) == 1
        assert result["schema"][0]["name"] == "context"

    def test_from_dict_pico(self):
        data = {
            "type": "pico",
            "fields": {
                "population": "patients",
                "intervention": "therapy",
                "comparison": "none",
                "outcome": "improvement",
            },
        }
        framework = Framework.from_dict(data)
        assert framework.type == FrameworkType.PICO
        assert framework.fields["population"] == "patients"
        assert framework.schema == ()

    def test_from_dict_spider(self):
        data = {
            "type": "spider",
            "fields": {"sample": "nurses", "phenomenon": "stress"},
        }
        framework = Framework.from_dict(data)
        assert framework.type == FrameworkType.SPIDER
        assert framework.fields["sample"] == "nurses"

    def test_from_dict_custom_with_schema(self):
        data = {
            "type": "custom",
            "fields": {"my_field": "my_value"},
            "schema": [
                {
                    "name": "my_field",
                    "category": "action",
                    "required": True,
                    "description": "Custom field",
                }
            ],
        }
        framework = Framework.from_dict(data)
        assert framework.type == FrameworkType.CUSTOM
        assert framework.fields["my_field"] == "my_value"
        assert len(framework.schema) == 1
        assert framework.schema[0].name == "my_field"
        assert framework.schema[0].category == FieldCategory.ACTION

    def test_roundtrip_pico(self):
        original = Framework(
            type=FrameworkType.PICO,
            fields={"population": "test", "intervention": "test"},
        )
        restored = Framework.from_dict(original.to_dict())
        assert restored == original

    def test_roundtrip_custom_with_schema(self):
        custom_schema = (
            FieldSchema(
                name="field1",
                category=FieldCategory.CONTEXT,
                required=True,
                description="First field",
            ),
            FieldSchema(
                name="field2",
                category=FieldCategory.RESULT,
                required=False,
                description="Second field",
            ),
        )
        original = Framework(
            type=FrameworkType.CUSTOM,
            fields={"field1": "value1", "field2": "value2"},
            schema=custom_schema,
        )
        restored = Framework.from_dict(original.to_dict())
        assert restored == original


class TestProtocolWithFramework:
    """Tests for Protocol dataclass with Framework integration."""

    def test_creation_with_pico_framework(self):
        framework = Framework(
            type=FrameworkType.PICO,
            fields={
                "population": "elderly",
                "intervention": "exercise",
                "comparison": "sedentary",
                "outcome": "health",
            },
        )
        protocol = Protocol(
            question="Does exercise improve health in elderly?",
            framework=framework,
            inclusion=("RCT", "peer-reviewed"),
            exclusion=("case studies",),
        )
        assert protocol.question == "Does exercise improve health in elderly?"
        assert protocol.framework.type == FrameworkType.PICO
        assert protocol.framework.fields["population"] == "elderly"
        assert protocol.inclusion == ("RCT", "peer-reviewed")
        assert protocol.exclusion == ("case studies",)

    def test_creation_with_spider_framework(self):
        framework = Framework(
            type=FrameworkType.SPIDER,
            fields={
                "sample": "teachers",
                "phenomenon": "remote learning",
                "design": "survey",
                "evaluation": "mixed methods",
                "research_type": "qualitative",
            },
        )
        protocol = Protocol(
            question="How do teachers experience remote learning?",
            framework=framework,
        )
        assert protocol.framework.type == FrameworkType.SPIDER
        assert protocol.framework.fields["sample"] == "teachers"

    def test_default_values(self):
        framework = Framework(type=FrameworkType.PICO, fields={})
        protocol = Protocol(question="Test?", framework=framework)
        assert protocol.inclusion == ()
        assert protocol.exclusion == ()
        assert protocol.databases == ("arxiv", "openalex", "semantic_scholar")
        assert protocol.year_range == ""

    def test_frozen(self):
        framework = Framework(type=FrameworkType.PICO, fields={})
        protocol = Protocol(question="Test?", framework=framework)
        with pytest.raises(AttributeError):
            protocol.question = "Changed?"

    def test_to_dict(self):
        framework = Framework(
            type=FrameworkType.PICO,
            fields={
                "population": "children",
                "intervention": "reading",
                "comparison": "no reading",
                "outcome": "literacy",
            },
        )
        protocol = Protocol(
            question="Does reading improve literacy?",
            framework=framework,
            inclusion=("schools",),
            exclusion=("adults",),
            databases=("arxiv", "openalex"),
            year_range="2020-2024",
        )
        result = protocol.to_dict()
        assert result["question"] == "Does reading improve literacy?"
        assert result["framework"]["type"] == "pico"
        assert result["framework"]["fields"]["population"] == "children"
        assert result["inclusion"] == ["schools"]
        assert result["exclusion"] == ["adults"]
        assert result["databases"] == ["arxiv", "openalex"]
        assert result["year_range"] == "2020-2024"

    def test_to_dict_custom_framework_with_schema(self):
        schema = (FieldSchema(name="custom_field", category=FieldCategory.ACTION),)
        framework = Framework(
            type=FrameworkType.CUSTOM,
            fields={"custom_field": "value"},
            schema=schema,
        )
        protocol = Protocol(question="Custom question?", framework=framework)
        result = protocol.to_dict()
        assert result["framework"]["type"] == "custom"
        assert "schema" in result["framework"]
        assert result["framework"]["schema"][0]["name"] == "custom_field"

    def test_from_dict(self):
        data = {
            "question": "Research question?",
            "framework": {
                "type": "spider",
                "fields": {"sample": "nurses", "phenomenon": "burnout"},
            },
            "inclusion": ["qualitative"],
            "exclusion": ["quantitative"],
            "databases": ["openalex"],
            "year_range": "2015-2023",
        }
        protocol = Protocol.from_dict(data)
        assert protocol.question == "Research question?"
        assert protocol.framework.type == FrameworkType.SPIDER
        assert protocol.framework.fields["sample"] == "nurses"
        assert protocol.inclusion == ("qualitative",)
        assert protocol.exclusion == ("quantitative",)
        assert protocol.databases == ("openalex",)
        assert protocol.year_range == "2015-2023"

    def test_from_dict_minimal(self):
        data = {
            "question": "Simple question?",
            "framework": {"type": "pico", "fields": {}},
        }
        protocol = Protocol.from_dict(data)
        assert protocol.question == "Simple question?"
        assert protocol.framework.type == FrameworkType.PICO
        assert protocol.inclusion == ()
        assert protocol.exclusion == ()
        assert protocol.databases == ("arxiv", "openalex", "semantic_scholar")

    def test_from_dict_custom_with_schema(self):
        data = {
            "question": "Custom framework question?",
            "framework": {
                "type": "custom",
                "fields": {"field1": "val1", "field2": "val2"},
                "schema": [
                    {"name": "field1", "category": "context", "required": True},
                    {"name": "field2", "category": "result", "required": False},
                ],
            },
        }
        protocol = Protocol.from_dict(data)
        assert protocol.framework.type == FrameworkType.CUSTOM
        assert len(protocol.framework.schema) == 2
        assert protocol.framework.schema[0].name == "field1"
        assert protocol.framework.schema[1].required is False

    def test_roundtrip(self):
        framework = Framework(
            type=FrameworkType.PICO,
            fields={
                "population": "athletes",
                "intervention": "training",
                "comparison": "rest",
                "outcome": "performance",
            },
        )
        original = Protocol(
            question="Training impact on performance?",
            framework=framework,
            inclusion=("RCT", "meta-analysis"),
            exclusion=("opinion pieces",),
            databases=("arxiv", "openalex", "semantic_scholar"),
            year_range="2018-2024",
        )
        restored = Protocol.from_dict(original.to_dict())
        assert restored == original

    def test_roundtrip_custom_framework(self):
        schema = (
            FieldSchema(
                name="context",
                category=FieldCategory.CONTEXT,
                required=True,
                description="Research context",
            ),
            FieldSchema(
                name="mechanism",
                category=FieldCategory.ACTION,
                required=True,
                description="Mechanism being studied",
            ),
            FieldSchema(
                name="outcome",
                category=FieldCategory.RESULT,
                required=False,
                description="Expected outcome",
            ),
        )
        framework = Framework(
            type=FrameworkType.CUSTOM,
            fields={
                "context": "educational",
                "mechanism": "gamification",
                "outcome": "engagement",
            },
            schema=schema,
        )
        original = Protocol(
            question="CMO question?",
            framework=framework,
            inclusion=("empirical studies",),
        )
        restored = Protocol.from_dict(original.to_dict())
        assert restored == original


class TestFrameworkTemplates:
    def test_pico_template_exists(self):
        from scimesh.vault.models import FRAMEWORK_TEMPLATES, FrameworkType

        assert FrameworkType.PICO in FRAMEWORK_TEMPLATES

    def test_pico_template_has_four_fields(self):
        from scimesh.vault.models import FRAMEWORK_TEMPLATES, FrameworkType

        pico = FRAMEWORK_TEMPLATES[FrameworkType.PICO]
        assert len(pico) == 4
        names = {f.name for f in pico}
        assert names == {"population", "intervention", "comparison", "outcome"}

    def test_spider_template_exists(self):
        from scimesh.vault.models import FRAMEWORK_TEMPLATES, FrameworkType

        assert FrameworkType.SPIDER in FRAMEWORK_TEMPLATES

    def test_spider_template_has_five_fields(self):
        from scimesh.vault.models import FRAMEWORK_TEMPLATES, FrameworkType

        spider = FRAMEWORK_TEMPLATES[FrameworkType.SPIDER]
        assert len(spider) == 5
        names = {f.name for f in spider}
        assert names == {"sample", "phenomenon", "design", "evaluation", "research_type"}

    def test_custom_not_in_templates(self):
        from scimesh.vault.models import FRAMEWORK_TEMPLATES, FrameworkType

        assert FrameworkType.CUSTOM not in FRAMEWORK_TEMPLATES
