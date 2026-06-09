#!/bin/bash
set -e

pnpm install --frozen-lockfile
pnpm --filter db push

# Auto-sync to GitHub after every merge
# Runs silently — skipped if GITHUB_TOKEN is not set
if [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "🔄 مزامنة تلقائية مع GitHub..."
    bash telegram-adder/push_to_github.sh && echo "✅ تمت المزامنة مع GitHub" || echo "⚠️ فشلت المزامنة — تحقق من GITHUB_TOKEN"
else
    echo "ℹ️ GITHUB_TOKEN غير موجود — تم تخطي المزامنة مع GitHub"
fi
