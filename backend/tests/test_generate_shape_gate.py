import unittest

from app.routers.generate import _validate_generated_code_shape


class GenerateShapeGateTests(unittest.TestCase):
    def test_rejects_csv_template_for_document(self) -> None:
        schema = {"input": [{"organizationName": "x"}]}
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const rows = parseCsv('');\n"
            "  return [];\n"
            "}\n"
        )
        with self.assertRaises(ValueError):
            _validate_generated_code_shape(code=code, schema_obj=schema, file_kind="pdf")

    def test_rejects_input_string_degradation(self) -> None:
        schema = {"input": [{"organizationName": "x"}]}
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const x = {\"input\":\"\"};\n"
            "  return [x as DealData];\n"
            "}\n"
        )
        with self.assertRaises(ValueError):
            _validate_generated_code_shape(code=code, schema_obj=schema, file_kind="docx")

    def test_rejects_value_scalar_when_input_wrapper_required(self) -> None:
        schema = {"input": [{"organizationName": "x"}]}
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const x = {\"value\":\"\"};\n"
            "  return [x as DealData];\n"
            "}\n"
        )
        with self.assertRaises(ValueError):
            _validate_generated_code_shape(code=code, schema_obj=schema, file_kind="docx")

    def test_accepts_basic_shape_with_input_key(self) -> None:
        schema = {"input": [{"organizationName": "x"}]}
        code = (
            "export default function (base64file: string): DealData[] {\n"
            "  const x = { input: [] };\n"
            "  return [x as DealData];\n"
            "}\n"
        )
        _validate_generated_code_shape(code=code, schema_obj=schema, file_kind="docx")


if __name__ == "__main__":
    unittest.main()
