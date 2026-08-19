.PHONY: demo test serve
demo:
	python -m congress_alpha demo
test:
	python -m pytest
serve:
	python -m congress_alpha serve
