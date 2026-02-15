import requests
try:
    res = requests.get('http://localhost:8000/api/knowledge/brands/3/graph').json()
    print(f"Nodes: {len(res.get('nodes', []))}")
    print(f"Edges: {len(res.get('edges', []))}")
    print(f"Stats: {res.get('stats')}")
except Exception as e:
    print(e)
