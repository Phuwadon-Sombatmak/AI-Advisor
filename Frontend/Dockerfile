FROM node:20-alpine

WORKDIR /app

# คัดลอกเฉพาะไฟล์ที่จำเป็นก่อน (เพื่อ cache)
COPY package.json ./

# ❌ อย่าใช้ npm ci (เพราะไม่มี lock)
# ✅ install ใน container ให้ตรง OS
RUN npm install

# คัดลอก source code ที่เหลือ
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
