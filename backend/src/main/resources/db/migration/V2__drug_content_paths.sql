ALTER TABLE medications.drugs
    ADD COLUMN IF NOT EXISTS source_file VARCHAR(255),
    ADD COLUMN IF NOT EXISTS details_html_path VARCHAR(1024),
    ADD COLUMN IF NOT EXISTS pack_image_path VARCHAR(1024);
