-- SPDA Institutional Data Blueprint (v2.0 - Multi-Component Scoring)
CREATE DATABASE IF NOT EXISTS SPDA;
USE SPDA;

-- 1. Institutional Student Registry
CREATE TABLE IF NOT EXISTS students (
    enrollment_no VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    semester INT,
    password_hash VARCHAR(255),
    is_password_changed BOOLEAN DEFAULT FALSE,
    profile_pic VARCHAR(255) DEFAULT 'default.png'
);

-- 2. Faculty Domain Registry
CREATE TABLE IF NOT EXISTS faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    password_hash VARCHAR(255)
);

-- 3. Academic Subject Matrix
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    semester INT,
    faculty_id INT,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
);

-- 4. Unified Performance Ledger (Refactored Schema)
CREATE TABLE IF NOT EXISTS marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    internal_marks INT,
    viva_marks INT,
    external_marks INT,
    total_marks INT,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- 5. Institutional Attendance Registry
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    date DATE,
    status ENUM('Present', 'Absent'),
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- 6. Pedagogical Feedback Hub
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE
);
