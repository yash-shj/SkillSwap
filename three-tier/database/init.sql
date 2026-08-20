CREATE DATABASE IF NOT EXISTS skillswap;
USE skillswap;

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    offered_skills JSON NOT NULL,
    wanted_skills JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    proposer_id INT NOT NULL,
    recipient_id INT NOT NULL,
    proposed_time VARCHAR(80) NOT NULL,
    status ENUM('proposed', 'confirmed') NOT NULL DEFAULT 'proposed',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposer_id) REFERENCES users(id),
    FOREIGN KEY (recipient_id) REFERENCES users(id)
);
