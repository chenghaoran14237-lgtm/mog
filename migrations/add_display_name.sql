-- 添加 display_name 字段到 extracted_documents 表
-- 执行日期: 2026-03-18

-- 添加字段
ALTER TABLE extracted_documents
ADD COLUMN display_name VARCHAR(255) NULL;

-- 添加注释
COMMENT ON COLUMN extracted_documents.display_name IS '用户自定义的文档显示名称';

-- 可选：为现有文档设置默认显示名称（基于文档ID）
-- UPDATE extracted_documents
-- SET display_name = '文档 #' || id::text
-- WHERE display_name IS NULL;
