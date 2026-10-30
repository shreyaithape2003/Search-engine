from app.evaluation.dataset import EVALUATION_QUERIES
from app.evaluation.runner import render_report, run_evaluation


def main() -> None:
    try:
        report = run_evaluation()
    except ValueError as error:
        raise SystemExit(f"Evaluation failed: {error}") from error
    print(render_report(report, EVALUATION_QUERIES))


if __name__ == "__main__":
    main()
