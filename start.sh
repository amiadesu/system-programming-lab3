#!/bin/bash

echo "Starting backend..."
cd backend
source .venv/bin/activate
uvicorn main:app --reload &
BACKEND_PID=$!
cd ..

echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

trap "echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID" EXIT

wait
