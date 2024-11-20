import os
import time
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pandas import DataFrame
from tqdm import tqdm

from CoT.groq_experiment import extract_edges_incident_format, compare_edges, aggregate_metrics, display_metrics
from CoT.prompt_generator import generate_few_shot_prompt


def run_single_experiment(client: OpenAI, df: DataFrame) -> Optional[dict]:
    """
    Run a single experiment to compare expected edges with the model's predicted edges.

    :param client: OpenAI API client.
    :param df: DataFrame containing the questions and expected answers.
    :return: A dictionary with the comparison result.
    """
    try:
        # Generate the prompt for LLM
        print("\nGenerating a few-shot prompt...")
        prompt_data = generate_few_shot_prompt(df, num_examples=3)
        prompt_content = "\n".join(prompt_data["standard_prompt"])

        # Expected answer
        new_question_index = prompt_data["new_question_index"]
        question_row = df.iloc[new_question_index]
        expected_answer = question_row["expected_answer"]

        # Extract edges from the expected answer
        expected_edges = extract_edges_incident_format(expected_answer)

        # Generate the answer using the OpenAI API
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are ChatGPT, an expert in causal inference and data analysis."
                },
                {
                    "role": "user",
                    "content": prompt_content
                }
            ]
        )

        # Debug: Print the model's response
        print("\nModel Response:")
        print(completion.choices[0].message.content)

        # Extract edges from the model's answer
        answer_edges = extract_edges_incident_format(completion.choices[0].message.content)

        # Compare the expected edges with the model's predicted edges
        return compare_edges(expected_edges, answer_edges)
    except Exception as e:
        print(f"Experiment failed: {e}")
        return None  # Skip the experiment if an error occurs


def run_multiple_experiments(client: OpenAI, df: DataFrame, num_experiments: int) -> None:
    """
    Run multiple experiments and calculate aggregate metrics.

    :param client: OpenAI API client.
    :param df: DataFrame containing the questions and expected answers.
    :param num_experiments: Number of experiments to run.
    """
    results = []
    failed_experiments = 0

    for _ in tqdm(range(num_experiments), desc="Running Experiments"):
        result = run_single_experiment(client, df)
        if result:
            results.append(result)
        else:
            failed_experiments += 1

        # Throttle the requests to avoid Groq rate limiting
        print("Throttling: Waiting for 1 minute and 5 seconds before the next request...")
        time.sleep(65)

    # Aggregate metrics from multiple experiments
    if results:
        aggregated_metrics = aggregate_metrics(results)
        display_metrics(aggregated_metrics)

    print(f"\nTotal failed experiments: {failed_experiments} out of {num_experiments}")


def main():
    # Retrieve the API key from the .env file
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable in your .env file.")

    # Load the dataframe
    script_directory = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_directory, "data/v0.0.3/train.csv")
    df = pd.read_csv(csv_file_path)

    # Initialize the GROQ client
    client = OpenAI(
        api_key=api_key,
    )

    # Run a single experiment
    #print(run_single_experiment(client, df))

    # Run multiple experiments
    run_multiple_experiments(client, df, num_experiments=50)


if __name__ == "__main__":
    main()