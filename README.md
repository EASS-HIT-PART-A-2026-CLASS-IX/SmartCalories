# Calorie tracker App

## Clone

```bash
git clone https://github.com/EASS-HIT-PART-A-2026-CLASS-IX/SmartCalories.git
cd SmartCalories
```

## Setup

Python 3.12+ and [uv](https://docs.astral.sh/uv/). Install once:  
`curl -LsSf https://astral.sh/uv/install.sh | sh` — then restart the shell or `export PATH="$HOME/.local/bin:$PATH"`.

```bash
cd backend
uv sync
```

## Run

```bash
uv run uvicorn calorie_tracker.main:app
```

Base URL: `http://127.0.0.1:9000` (adjust if you change host/port).

### Interactive docs (no `curl`)

Open [http://127.0.0.1:9000/docs](http://127.0.0.1:9000/docs) (Swagger UI): **Try it out** → **Execute** on each route. ReDoc: `/redoc`.

### `curl` examples

```bash
curl -s http://127.0.0.1:9000/health
```
```bash
curl -s http://127.0.0.1:9000/entries
```
```bash
curl -s -X POST http://127.0.0.1:9000/entries \
  -H "Content-Type: application/json" \
  -d '{"name":"Oatmeal","calories":150,"meal":"breakfast"}'
```
```bash
curl -s http://127.0.0.1:9000/entries/1
```
```bash
curl -s -X PUT http://127.0.0.1:9000/entries/1 \
  -H "Content-Type: application/json" \
  -d '{"name":"Oatmeal with berries","calories":220,"meal":"breakfast"}'
```
```bash
curl -s -X DELETE http://127.0.0.1:9000/entries/1
```

Optional: append `| python -m json.tool` to pretty-print JSON.

## Seed sample entries

With the server running (make sure you are on the backend folder):

```bash
uv run python -m calorie_tracker.scripts.seed
```

Another port/host: `BASE_URL=http://localhost:8001 uv run python -m calorie_tracker.scripts.seed`

## Tests

```bash
uv run pytest
```

## REST Client (`.http` file)

Install the **REST Client** extension so you can run requests from the editor:  
[REST Client on Open VSX (Cursor)](https://marketplace.cursorapi.com/items/?itemName=humao.rest-client).

Open `examples.http` in this folder with the API running, then use **Send Request** above each request block to execute it and see the response beside your file.