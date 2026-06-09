#!/bin/bash
# GitHub Auto-Sync Daemon
# يعمل كـ background process في Replit ("GitHub Auto-Sync" workflow)
#
# السلوك:
#   - كل SYNC_INTERVAL ثانية (افتراضي: 60):
#       1. تغييرات غير محفوظة في working tree → auto-commit تلقائي
#       2. أي commit لم يُرفع بعد → push تلقائي
#   - يضمن أن GitHub دائماً يعكس آخر حالة للكود
#
# متطلبات GITHUB_TOKEN:
#   - النطاق "repo"     — للوصول الكامل للـ repository
#   - النطاق "workflow" — لرفع ملفات .github/workflows/ (اختياري)
#   بدون "workflow": يُرفع كل شيء ما عدا .github/workflows/
#   صنع token: https://github.com/settings/tokens

REPO="v8488336-sys/Add"
INTERVAL="${SYNC_INTERVAL:-60}"
LAST_PUSHED_SHA=""
LOG_PREFIX="[GitHub-Sync]"
WORKFLOW_SCOPE_OK=true   # يُضبط false عند اكتشاف غياب النطاق

if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "$LOG_PREFIX ❌ GITHUB_TOKEN غير موجود"
    echo "$LOG_PREFIX أضفه في: Replit → Secrets → GITHUB_TOKEN"
    echo "$LOG_PREFIX صنع token: https://github.com/settings/tokens"
    exit 1
fi

ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$ROOT" || exit 1

git config user.email "bot@tgadder.pro"
git config user.name "Telegram Adder Pro"

REMOTE_URL="https://x-token-auth:${GITHUB_TOKEN}@github.com/${REPO}.git"

setup_remote() {
    git remote remove github 2>/dev/null || true
    git remote add github "$REMOTE_URL"
}

get_github_sha() {
    git ls-remote github refs/heads/main 2>/dev/null | awk '{print $1}' || echo ""
}

has_uncommitted_changes() {
    ! git diff-index --quiet HEAD -- 2>/dev/null \
        || [ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]
}

auto_commit_if_dirty() {
    if has_uncommitted_changes; then
        local ts
        ts=$(date -u '+%Y-%m-%d %H:%M UTC')
        echo "$LOG_PREFIX 💾 تغييرات غير محفوظة — auto-commit..."
        git add -A
        if git commit -m "chore: auto-save — ${ts}" --no-verify -q 2>&1; then
            echo "$LOG_PREFIX ✅ auto-commit: $(git rev-parse --short HEAD)"
        else
            echo "$LOG_PREFIX ⚠️ فشل auto-commit"
        fi
    fi
}

do_push() {
    local branch="$1"
    git fetch github main --no-tags -q 2>/dev/null || true
    git push github "${branch}:main" --force-with-lease=main:github/main 2>&1 \
        || git push github "${branch}:main" --force 2>&1
}

push_to_github() {
    local local_sha="$1"
    local short="${local_sha:0:7}"
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

    echo "$LOG_PREFIX 📤 رفع commit ${short} على GitHub..."
    local push_out
    push_out=$(do_push "$branch")
    local push_exit=$?

    # اكتشاف خطأ workflow scope
    if echo "$push_out" | grep -q "workflow.*scope\|without.*workflow"; then
        if $WORKFLOW_SCOPE_OK; then
            echo "$LOG_PREFIX ⚠️ الـ token لا يملك نطاق 'workflow' — سيُرفع كل شيء ما عدا .github/workflows/"
            echo "$LOG_PREFIX   لتفعيل الرفع الكامل: https://github.com/settings/tokens → ✅ workflow"
            WORKFLOW_SCOPE_OK=false
        fi

        # Fallback: رفع بدون .github/workflows/ عبر snapshot
        local tmpdir
        tmpdir=$(mktemp -d)
        git archive HEAD | tar -x -C "$tmpdir"
        rm -rf "$tmpdir/.github/workflows"

        push_out=$(
            cd "$tmpdir" || exit 1
            git init -b main -q
            git config user.email "bot@tgadder.pro"
            git config user.name "Telegram Adder Pro"
            git add -A
            git commit -m "chore: auto-sync from Replit — ${short} — $(date -u '+%Y-%m-%d %H:%M UTC')" -q
            git remote add origin "$REMOTE_URL"
            git push origin main --force 2>&1
        )
        push_exit=$?
        rm -rf "$tmpdir"
    fi

    if [ $push_exit -eq 0 ]; then
        sleep 3
        local remote_sha
        remote_sha=$(get_github_sha)
        if [ -n "$remote_sha" ]; then
            echo "$LOG_PREFIX ✅ تمت المزامنة — https://github.com/${REPO}"
            echo "$LOG_PREFIX ✔ GitHub HEAD: ${remote_sha:0:7}"
            LAST_PUSHED_SHA="$local_sha"
            return 0
        fi
    fi

    echo "$LOG_PREFIX ⚠️ فشل الرفع — سيُعاد المحاولة خلال ${INTERVAL}ث"
    return 1
}

# ─── الإعداد الأولي ───────────────────────────────────────────────
setup_remote
echo "$LOG_PREFIX 🚀 بدأ الـ daemon — يفحص كل ${INTERVAL} ثانية"
echo "$LOG_PREFIX 🎯 الهدف: https://github.com/${REPO}"
echo "$LOG_PREFIX 📝 يُرفع تلقائياً: التغييرات غير المحفوظة + كل commit جديد"

# ─── الحلقة الرئيسية ─────────────────────────────────────────────
while true; do
    # الخطوة 1: auto-commit لأي تغييرات في الـ working tree
    auto_commit_if_dirty

    # الخطوة 2: رفع أي commit لم يصل إلى GitHub بعد
    LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")

    if [ -n "$LOCAL_SHA" ] && [ "$LOCAL_SHA" != "$LAST_PUSHED_SHA" ]; then
        REMOTE_SHA=$(get_github_sha)

        if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
            echo "$LOG_PREFIX ✓ GitHub محدّث (${LOCAL_SHA:0:7}) — لا حاجة للرفع"
            LAST_PUSHED_SHA="$LOCAL_SHA"
        else
            push_to_github "$LOCAL_SHA" || true
        fi
    fi

    sleep "$INTERVAL"
done
