import click
import logging
import pandas as pd
from pathlib import Path

from .config import EvalConfig, DEFAULT_CONFIG, logger
from .collect import collect_responses, collect_raw_evaluations
from .parse import parse_evaluation_rows
from .rank import build_endorsement_graph, compute_pagerank, finalize_rankings

@click.command()
@click.option('--prompts', default='prompts.xlsx', help='Path to prompts Excel file')
@click.option('--output-dir', default='results', help='Output directory for results')
@click.option('--models', help='Comma-separated list of models to evaluate')
def main(prompts, output_dir, models):
    """
    Run the full SlopRank evaluation workflow.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    model_list = models.split(',') if models else None
    config = EvalConfig(
        model_names=model_list or DEFAULT_CONFIG.model_names,
        evaluation_method=1,  # numeric rating
        use_subset_evaluation=True,
        evaluators_subset_size=3,
        output_dir=Path(output_dir)
    )
    logger.info(f"Using config: {config}")

    # 1) Read prompts
    prompts_df = pd.read_excel(prompts)
    prompt_pairs = list(zip(
        prompts_df["Questions"].tolist(),
        prompts_df["Answer_key"].tolist() if "Answer_key" in prompts_df.columns else [None]*len(prompts_df)
    ))

    # 2) Collect responses
    responses_df = collect_responses(prompt_pairs, config)

    # 3) Collect raw evaluations
    raw_eval_df = collect_raw_evaluations(responses_df, config)

    # 4) Parse evaluation rows
    eval_path = config.output_dir / "evaluations.csv"
    if eval_path.exists():
        logger.info(f"Loading existing parsed evaluations from {eval_path}")
        evaluations_df = pd.read_csv(eval_path)
    else:
        evaluations_df = parse_evaluation_rows(raw_eval_df, config)
        evaluations_df.to_csv(eval_path, index=False)
        logger.info(f"Saved parsed evaluations to {eval_path}")

    # 5) Build and rank
    G = build_endorsement_graph(evaluations_df, config)
    pagerank_scores = compute_pagerank(G)
    finalize_rankings(pagerank_scores, config)
