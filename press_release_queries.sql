-- =====================================================
-- SQL QUERIES FOR PRESS RELEASES DATA
-- =====================================================

-- 1. VIEW ALL PRESS RELEASES (Basic Query)
-- =========================================
SELECT 
    id,
    press_release_title as "TITLE",
    press_release_date as "DATE", 
    pdf_press_release_link_public_link as "PDF_URL",
    created_at as "SCRAPED_AT"
FROM fda_recalls 
WHERE entry_type = 'press_release' 
ORDER BY press_release_date DESC;

-- 2. VIEW ALL PRESS RELEASES WITH TEXT LENGTH
-- ===========================================
SELECT 
    id,
    press_release_title as "TITLE",
    press_release_date as "DATE",
    pdf_press_release_link_public_link as "PDF_URL",
    CASE 
        WHEN all_text IS NOT NULL THEN LENGTH(all_text)
        ELSE 0 
    END as "TEXT_LENGTH",
    created_at as "SCRAPED_AT"
FROM fda_recalls 
WHERE entry_type = 'press_release' 
ORDER BY press_release_date DESC;

-- 3. VIEW PRESS RELEASES WITH TEXT SAMPLE
-- =======================================
SELECT 
    id,
    press_release_title as "TITLE",
    press_release_date as "DATE",
    pdf_press_release_link_public_link as "PDF_URL",
    LENGTH(all_text) as "TEXT_LENGTH",
    LEFT(all_text, 200) as "TEXT_PREVIEW",
    created_at as "SCRAPED_AT"
FROM fda_recalls 
WHERE entry_type = 'press_release' 
AND all_text IS NOT NULL
ORDER BY press_release_date DESC;

-- 4. COMPREHENSIVE VIEW WITH ALL COLUMNS
-- =====================================
SELECT 
    id,
    entry_type,
    press_release_title,
    press_release_date,
    pdf_press_release_link_public_link,
    pdf_path,
    CASE 
        WHEN all_text IS NOT NULL THEN LENGTH(all_text)
        ELSE 0 
    END as text_length,
    created_at
FROM fda_recalls 
WHERE entry_type = 'press_release'
ORDER BY press_release_date DESC;

-- 5. SEARCH PRESS RELEASES BY KEYWORD IN TITLE
-- ============================================
SELECT 
    press_release_title as "TITLE",
    press_release_date as "DATE",
    pdf_press_release_link_public_link as "PDF_URL"
FROM fda_recalls 
WHERE entry_type = 'press_release' 
AND press_release_title ILIKE '%covid%'  -- Change 'covid' to your keyword
ORDER BY press_release_date DESC;

-- 6. SEARCH PRESS RELEASES BY KEYWORD IN TEXT CONTENT
-- ===================================================
SELECT 
    press_release_title as "TITLE",
    press_release_date as "DATE",
    pdf_press_release_link_public_link as "PDF_URL",
    LENGTH(all_text) as "TEXT_LENGTH"
FROM fda_recalls 
WHERE entry_type = 'press_release' 
AND all_text ILIKE '%vaccine%'  -- Change 'vaccine' to your keyword
ORDER BY press_release_date DESC;

-- 7. PRESS RELEASES BY DATE RANGE
-- ===============================
SELECT 
    press_release_title as "TITLE",
    press_release_date as "DATE",
    pdf_press_release_link_public_link as "PDF_URL"
FROM fda_recalls 
WHERE entry_type = 'press_release' 
AND press_release_date BETWEEN '2024-01-01' AND '2025-12-31'
ORDER BY press_release_date DESC;

-- 8. STATISTICS SUMMARY
-- ====================
SELECT 
    COUNT(*) as "TOTAL_PRESS_RELEASES",
    COUNT(press_release_title) as "WITH_TITLE",
    COUNT(press_release_date) as "WITH_DATE", 
    COUNT(pdf_press_release_link_public_link) as "WITH_PDF_LINK",
    COUNT(all_text) as "WITH_TEXT",
    AVG(LENGTH(all_text)) as "AVG_TEXT_LENGTH",
    MIN(press_release_date) as "OLDEST_DATE",
    MAX(press_release_date) as "NEWEST_DATE"
FROM fda_recalls 
WHERE entry_type = 'press_release';

-- 9. FULL TEXT EXPORT (Use carefully - can be large)
-- ==================================================
SELECT 
    press_release_title,
    press_release_date,
    all_text
FROM fda_recalls 
WHERE entry_type = 'press_release' 
AND all_text IS NOT NULL
ORDER BY press_release_date DESC;

-- 10. PRESS RELEASES WITHOUT EXTRACTED TEXT (For debugging)
-- =========================================================
SELECT 
    id,
    press_release_title,
    press_release_date,
    pdf_press_release_link_public_link,
    pdf_path
FROM fda_recalls 
WHERE entry_type = 'press_release' 
AND (all_text IS NULL OR LENGTH(all_text) < 10)
ORDER BY created_at DESC;
