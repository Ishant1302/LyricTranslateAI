package com.lyrictranslate.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;

import java.util.List;
import java.util.concurrent.Executor;

/**
 * AppConfig — Spring configuration for CORS and the async thread pool.
 *
 * Replaces:
 *   • FastAPI CORSMiddleware (allow localhost:5173)
 *   • ThreadPoolExecutor(max_workers=2) from main.py lifespan
 */
@Configuration
public class AppConfig {

    /**
     * CORS filter — allows the Vite dev server (localhost:5173) to call /api/*.
     * Equivalent of FastAPI's CORSMiddleware config in main.py.
     */
    @Bean
    public CorsFilter corsFilter() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(List.of(
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173"
        ));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return new CorsFilter(source);
    }

    /**
     * Thread pool for @Async pipeline tasks.
     * Equivalent of ThreadPoolExecutor(max_workers=2) in main.py lifespan.
     */
    @Bean(name = "pipelineExecutor")
    public Executor pipelineExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(2);
        executor.setMaxPoolSize(4);
        executor.setQueueCapacity(10);
        executor.setThreadNamePrefix("pipeline-");
        executor.initialize();
        return executor;
    }
}
