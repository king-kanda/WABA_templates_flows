.PHONY: run seed install clean

install:
	pip install -r requirements.txt

seed:
	python -m app.data.seed_vehicles

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -f data/car_rental.db
	rm -rf uploads/*
	@echo "Cleaned database and uploads"
