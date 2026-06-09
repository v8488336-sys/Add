#!/bin/bash
# سكريبت رفع المشروع على GitHub
# شغّله يدوياً: bash telegram-adder/push_to_github.sh
# أو يُستدعى تلقائياً من post-merge.sh
#
# متطلبات GITHUB_TOKEN:
#   - النطاق "repo"     (للوصول الكامل للـ repository)
#   - النطاق "workflow" (لرفع ملفات .github/workflows/)
# اصنع/جدّد token من: https://github.com/settings/tokens

GH_TOKEN="${GITHUB_TOKEN:-}"
REPO="v8488336-sys/Add"
REMOTE_URL="https://x-token-auth:${GH_TOKEN}@github.com/${REPO}.git"

if [ -z "$GH_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN غير موجود"
    echo "أضفه في: Replit → Secrets → GITHUB_TOKEN"
    echo "النطاقات المطلوبة: repo + workflow"
    exit 1
fi

ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$ROOT" || exit 1

git config user.email "bot@tgadder.pro"
git config user.name "Telegram Adder Pro"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
LOCAL_SHA=$(git rev-parse HEAD)
SHORT="${LOCAL_SHA:0:7}"

git remote remove github 2>/dev/null || true
git remote add github "$REMOTE_URL"

# تحديث remote tracking refs للـ force-with-lease
git fetch github main --no-tags -q 2>/dev/null || true

echo "📤 رفع commit ${SHORT} على GitHub (${REPO})..."
PUSH_OUT=$(git push github "${BRANCH}:main" --force-with-lease=main:github/main 2>&1) \
    || PUSH_OUT=$(git push github "${BRANCH}:main" --force 2>&1) \
    || { 
        if echo "$PUSH_OUT" | grep -q "workflow.*scope\|without.*workflow"; then
            echo "❌ الـ token لا يملك نطاق 'workflow'"
            echo "الحل: أعد توليد GITHUB_TOKEN من:"
            echo "  https://github.com/settings/tokens"
            echo "  ✅ فعّل: repo  ✅ فعّل: workflow"
        else
            echo "❌ فشل الرفع:"
            echo "$PUSH_OUT"
        fi
        exit 1
    }

echo "$PUSH_OUT"
echo "✅ تم الرفع بنجاح على https://github.com/${REPO}"

# تحقق من التطابق عبر ls-remote
REMOTE_SHA=$(git ls-remote github refs/heads/main 2>/dev/null | awk '{print $1}')
if [ -n "$REMOTE_SHA" ]; then
    echo "✔ GitHub HEAD: ${REMOTE_SHA:0:7}"
else
    echo "⚠️ تعذّر التحقق من SHA — تحقق يدوياً من GitHub"
fi
