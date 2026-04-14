<<<<<<< HEAD
-- 🎯 Student Performance Data Analysis System (SPDA) - Standardized Schema
-- Optimized for Flask + MySQL

-- 1️⃣ Database Strategy
CREATE DATABASE IF NOT EXISTS SPDA;
USE SPDA;

-- 2️⃣ Admin Identity Module
CREATE TABLE IF NOT EXISTS admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);

-- 3️⃣ Student Registry Module
=======
-- SPDA Institutional Data Blueprint (v2.0 - Multi-Component Scoring)
CREATE DATABASE IF NOT EXISTS SPDA;
USE SPDA;

-- 1. Institutional Student Registry
>>>>>>> student-panel
CREATE TABLE IF NOT EXISTS students (
    enrollment_no VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    semester INT,
    password_hash VARCHAR(255),
    is_password_changed BOOLEAN DEFAULT FALSE,
<<<<<<< HEAD
    phone VARCHAR(20),
    contact_no VARCHAR(15)
);

-- 4️⃣ Faculty & Curriculum Module
=======
    profile_pic VARCHAR(255) DEFAULT 'default.png'
);

-- 2. Faculty Domain Registry
>>>>>>> student-panel
CREATE TABLE IF NOT EXISTS faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
<<<<<<< HEAD
    department VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_code VARCHAR(20),
    subject_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    semester INT,
    credits INT,
=======
    department VARCHAR(50),
    password_hash VARCHAR(255)
);

-- 3. Academic Subject Matrix
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    semester INT,
>>>>>>> student-panel
    faculty_id INT,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
);

<<<<<<< HEAD
-- 5️⃣ Academic Performance Module
=======
-- 4. Unified Performance Ledger (Refactored Schema)
>>>>>>> student-panel
CREATE TABLE IF NOT EXISTS marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
<<<<<<< HEAD
    internal_marks INT DEFAULT 0,
    viva_marks INT DEFAULT 0,
    external_marks INT DEFAULT 0,
    total_marks INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
=======
    internal_marks INT,
    viva_marks INT,
    external_marks INT,
    total_marks INT,
>>>>>>> student-panel
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

<<<<<<< HEAD
-- 6️⃣ Institutional Attendance Module
=======
-- 5. Institutional Attendance Registry
>>>>>>> student-panel
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    date DATE,
<<<<<<< HEAD
    status VARCHAR(20),
=======
    status ENUM('Present', 'Absent'),
>>>>>>> student-panel
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

<<<<<<< HEAD
-- 7️⃣ Student Engagement Module (Feedback)
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(50),
    subject VARCHAR(255),
    message TEXT,
    type VARCHAR(50),
    status VARCHAR(50),
    admin_reply TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
=======
-- 6. Pedagogical Feedback Hub
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE
>>>>>>> student-panel
);
