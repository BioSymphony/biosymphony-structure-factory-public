import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "modules" / "schemas" / "provider-run.v1.schema.json"
FIXTURES = {
    "fal_serverless": ROOT / "examples" / "orchestration-fixtures" / "provider-run-fal-serverless.synthetic.json",
    "modal_function": ROOT / "examples" / "orchestration-fixtures" / "provider-run-modal-function.synthetic.json",
    "lambda_cloud": ROOT / "examples" / "orchestration-fixtures" / "provider-run-lambda-cloud.synthetic.json",
}


class ProviderRunSchemaTests(unittest.TestCase):
    def test_schema_covers_public_provider_profiles(self) -> None:
        schema = json.loads(SCHEMA.read_text())
        providers = set(schema["properties"]["provider"]["enum"])

        for profile_path in (ROOT / "modules" / "provider-profiles").glob("**/*.json"):
            profile = json.loads(profile_path.read_text())
            self.assertIn(profile["provider"], providers, profile_path.relative_to(ROOT))

        self.assertLessEqual(
            {
                "runpod",
                "runpod_serverless",
                "aws",
                "aws_batch",
                "ssh_hpc",
                "generic_cloud",
                "neocloud_gpu_pod",
                "fal",
                "fal-serverless",
                "modal",
                "modal_function",
                "lambda",
                "lambda_cloud",
                "provider_neutral",
            },
            providers,
        )

        self.assertEqual(
            {
                "planning",
                "public_demo",
                "public_synthetic_demo",
                "computational_candidate",
                "candidate",
                "blocked",
                "insufficient_evidence",
                "insufficient_support",
            },
            set(schema["properties"]["result_boundary"]["enum"]),
        )
        self.assertIn("public_data", schema["properties"]["source_posture"]["enum"])
        self.assertIn("provider_native", schema["properties"]["source_posture"]["enum"])

    def test_safe_fal_modal_and_lambda_fixtures_validate(self) -> None:
        schema = json.loads(SCHEMA.read_text())
        providers = set(schema["properties"]["provider"]["enum"])

        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is optional")

        validator = Draft202012Validator(schema)
        for provider, fixture_path in FIXTURES.items():
            with self.subTest(provider=provider):
                fixture = json.loads(fixture_path.read_text())
                self.assertEqual(provider, fixture["provider"])
                self.assertEqual("planned", fixture["status"])
                self.assertEqual("public_synthetic_demo", fixture["result_boundary"])
                self.assertIsNone(fixture["provider_run_id"])
                self.assertEqual([], fixture["errors"])
                self.assertIn(provider, providers)
                self.assertTrue(validator.is_valid(fixture), list(validator.iter_errors(fixture)))
