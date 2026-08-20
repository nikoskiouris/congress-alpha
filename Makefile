.PHONY: demo test serve brief ingest-fixture
demo:
	python -m congress_alpha demo
test:
	python -m pytest
serve:
	python -m congress_alpha serve
brief:
	python -m congress_alpha brief --dash data/dashboard.json --out data/research_brief.md
ingest-fixture:
	python -m congress_alpha ingest --trades data/fixtures/trades_ok.json --prices data/fixtures/prices.csv --politicians data/fixtures/politicians.json --securities data/fixtures/securities.json --committees data/fixtures/committees.json --db data/congress_alpha.db
