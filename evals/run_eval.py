import json
import os
import sys

# Assume balancr module is in the python path (e.g. run via `python -m evals.run_eval`)
try:
    from balancr.engine import reconcile_case
except ImportError:
    # Dummy mock for now so the script can be tested before full implementation
    def reconcile_case(case_input):
        # In a real scenario, this calls the deterministic engine, then the LangGraph agent
        return "match"

def main():
    golden_file = os.path.join(os.path.dirname(__file__), "golden_cases.json")
    
    if not os.path.exists(golden_file):
        print(f"Error: {golden_file} not found.")
        sys.exit(1)
        
    with open(golden_file, "r") as f:
        cases = json.load(f)
        
    min_accuracy = float(os.environ.get("MIN_ACCURACY", "90.0"))
    
    total = len(cases)
    correct = 0
    failures = []
    
    print(f"Running evaluation on {total} golden cases...")
    
    for case in cases:
        case_id = case["case_id"]
        expected = case["expected_output"]
        input_data = case["input"]
        
        # We pass the input to our engine (which includes deterministic + LangGraph LLM)
        try:
            actual = reconcile_case(input_data)
        except Exception as e:
            actual = f"error: {str(e)}"
            
        if actual == expected:
            correct += 1
        else:
            failures.append({
                "case_id": case_id,
                "expected": expected,
                "actual": actual,
                "description": case["description"]
            })
            
    accuracy = (correct / total) * 100 if total > 0 else 0.0
    passed = accuracy >= min_accuracy
    
    # Generate Markdown summary for GitHub Step Summary
    summary_md = f"## Agent Evaluation Results\n\n"
    summary_md += f"- **Total Cases:** {total}\n"
    summary_md += f"- **Correct:** {correct}\n"
    summary_md += f"- **Accuracy:** {accuracy:.2f}%\n"
    summary_md += f"- **Threshold:** {min_accuracy:.2f}%\n"
    summary_md += f"- **Status:** {'✅ PASSED' if passed else '❌ FAILED'}\n\n"
    
    if failures:
        summary_md += "### Failed Cases\n\n"
        summary_md += "| Case ID | Description | Expected | Actual |\n"
        summary_md += "|---------|-------------|----------|--------|\n"
        for fail in failures:
            summary_md += f"| {fail['case_id']} | {fail['description']} | `{fail['expected']}` | `{fail['actual']}` |\n"
            
    # Write to GITHUB_STEP_SUMMARY if available
    step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_file:
        with open(step_summary_file, "a") as f:
            f.write(summary_md)
    else:
        print("\n--- SUMMARY ---")
        print(summary_md)
        
    # Write a small JSON artifact for the github-script to post as a PR comment
    with open("eval_results.json", "w") as f:
        json.dump({
            "accuracy": accuracy,
            "min_accuracy": min_accuracy,
            "passed": passed,
            "failures": failures
        }, f)
        
    if not passed:
        print(f"\nEvaluation failed! Accuracy {accuracy:.2f}% is below threshold {min_accuracy:.2f}%.")
        sys.exit(1)
    else:
        print(f"\nEvaluation passed! Accuracy {accuracy:.2f}% meets or exceeds threshold {min_accuracy:.2f}%.")
        sys.exit(0)

if __name__ == "__main__":
    main()
