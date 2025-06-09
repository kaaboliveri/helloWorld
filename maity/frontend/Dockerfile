# Stage 1: Build the React/Vue app
FROM node:18-alpine as builder
WORKDIR /app
COPY package.json ./
# Use pnpm or yarn if preferred
RUN npm install
COPY . .
# Replace 'build' with your actual build script from package.json
RUN npm run build

# Stage 2: Serve the static files with Nginx
FROM nginx:stable-alpine
# Copy built assets from builder stage
COPY --from=builder /app/build /usr/share/nginx/html # Adjust '/app/build' to your build output dir
# Copy custom nginx config if needed (for SPA routing)
# COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
