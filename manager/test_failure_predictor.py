
from failure_predictor import analyze_container_history


def make_history(memory, cpu):
    return [
        {
            "id": index + 1,
            "memory_percent": memory[index],
            "cpu_percent": cpu[index],
        }
        for index in range(3)
    ]


test_cases = [
    {
        "name": "Low Risk",
        "history": make_history(
            [10, 11, 12],
            [10, 12, 15],
        ),
    },
    {
        "name": "Medium Risk",
        "history": make_history(
            [20, 35, 55],
            [10, 12, 15],
        ),
    },
    {
        "name": "High Risk",
        "history": make_history(
            [60, 75, 90],
            [90, 92, 95],
        ),
    },
]


for case in test_cases:
    result = analyze_container_history(
        case["name"],
        case["history"],
    )

    print("\nTest:", case["name"])
    print("Detected risk:", result["risk_level"])
    print("Risk score:", result["risk_score"])
    print("Findings:", result["findings"])
