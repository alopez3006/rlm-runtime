#!/usr/bin/env python3
"""
Data Analysis Example with RLM Runtime

This example demonstrates using RLM Runtime for data analysis tasks,
including CSV processing and generating reports.
"""

import asyncio
import tempfile
from pathlib import Path

from rlm import RLM


async def main():
    """Run data analysis examples."""
    # Create RLM with Docker for better isolation
    rlm = RLM(
        model="gpt-4o-mini",
        environment="docker",
        max_depth=6,
        docker_memory="1g",
    )

    # Create sample data
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("""name,age,department,salary
Alice,30,Engineering,85000
Bob,25,Marketing,65000
Charlie,35,Engineering,95000
Diana,28,Sales,70000
Eve,32,Engineering,88000
Frank,40,Management,120000
Grace,27,Marketing,62000
""")
        csv_path = f.name

    try:
        # Analyze the data
        print("=== Data Analysis ===")
        result = await rlm.completion(f"""
            Analyze the CSV file at {csv_path}:
            1. Load the data
            2. Calculate average salary by department
            3. Find the highest paid employee
            4. Count employees per department
            5. Create a summary report
        """)
        print(result.response)
        print()

        # Generate insights
        print("=== Generate Insights ===")
        result = await rlm.completion(f"""
            From the employee data in {csv_path}:
            1. Identify any salary outliers
            2. Calculate the salary range
            3. What percentage of employees are in Engineering?
            4. Suggest if any departments are underpaid
        """)
        print(result.response)
        print()

    finally:
        # Cleanup
        Path(csv_path).unlink()


if __name__ == "__main__":
    asyncio.run(main())
