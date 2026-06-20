package com.lyrictranslate;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

import java.nio.file.Files;
import java.nio.file.Paths;

/**
 * LyricTranslate AI — Spring Boot entry point.
 *
 * Equivalent of: uvicorn.run("main:app", host="0.0.0.0", port=8000)
 *
 * @EnableAsync enables background pipeline execution via @Async methods,
 * replacing FastAPI's loop.run_in_executor(executor, ...) pattern.
 */
@SpringBootApplication
@EnableAsync
public class LyricTranslateApplication {

    public static void main(String[] args) throws Exception {
        // Ensure upload / cache directories exist (same as Python's Path.mkdir)
        Files.createDirectories(Paths.get("uploads"));
        Files.createDirectories(Paths.get("cache"));

        SpringApplication.run(LyricTranslateApplication.class, args);
        System.out.println("[OK] LyricTranslate AI backend started on port 8000");
    }
}
