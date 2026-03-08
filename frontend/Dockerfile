FROM node:20-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

EXPOSE 5173

# Run Vite dev server (accessible from host)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
