.PHONY: run migrate makemigrations seed test lint clean

run:
	python manage.py runserver 127.0.0.1:8000

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

seed:
	python manage.py seed_demo_data

test:
	python manage.py test tests

lint:
	python -m flake8 apps config tests || true

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
