import requests
r = requests.get('http://localhost:8000/api/book/progress/09314f74-0faa-4661-a903-19a767ef5797')
j = r.json()
print("--- RAW JSON KEYS ---")
print(list(j.keys()))
print()
print("--- KEY VALUES ---")
print(f"current_step: {j.get('current_step')}")
print(f"total_steps: {j.get('total_steps')}")
print(f"estimated_time_minutes: {j.get('estimated_time_minutes')}")
print(f"estimated_time_confidence: {j.get('estimated_time_confidence')}")
print(f"is_complete: {j.get('is_complete')}")


