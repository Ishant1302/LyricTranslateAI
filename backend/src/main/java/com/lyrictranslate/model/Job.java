package com.lyrictranslate.model;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.Map;

/**
 * Job — POJO representing one audio processing job.
 *
 * Direct Java equivalent of the dict created in jobs_store.py::create_job().
 * Fields map 1-to-1 with the JSON shape the frontend polls for.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Job {

    public String  id;
    public String  status;      // "processing" | "complete" | "error"
    public int     progress;    // 0–100
    public String  step;
    public String  error;
    public Object  result;      // final lyric JSON (only when complete)
    public String  filePath;    // local path to uploaded audio file
    public String  vocalsPath;  // path to Demucs-isolated vocals
    public Object  segments;    // raw transcription segments (intermediate)
    public Map<String, Object> metadata;  // title, artist, language …

    /** Default constructor required by Jackson */
    public Job() {}

    public Job(String id, Map<String, Object> metadata) {
        this.id       = id;
        this.status   = "processing";
        this.progress = 0;
        this.step     = "Uploading";
        this.error    = null;
        this.result   = null;
        this.filePath = null;
        this.vocalsPath = null;
        this.segments = null;
        this.metadata = metadata;
    }
}
