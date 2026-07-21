.PHONY: install install-backend install-frontend dev dev-backend dev-frontend test

install: install-backend install-frontend

install-backend:
	cd backend && pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Run both concurrently (requires 'make' + two terminals, or use 'concurrently')
dev:
	@echo "Start backend:  make dev-backend"
	@echo "Start frontend: make dev-frontend"

test:
	cd backend && python -m pytest tests/ -v
