package kz.cashguard.storage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import kz.cashguard.config.AppProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

@Component
public class VideoStorage {

    static final Set<String> ALLOWED_EXTENSIONS = Set.of("mov", "mp4");
    private static final Logger log = LoggerFactory.getLogger(VideoStorage.class);

    private final Path dir;
    private final long maxBytes;

    public VideoStorage(AppProperties properties) {
        this.dir = Path.of(properties.storage().dir()).toAbsolutePath();
        this.maxBytes = properties.storage().maxUpload().toBytes();
    }

    public Path save(MultipartFile file) {
        String extension = validate(file);
        try {
            Files.createDirectories(dir);
            Path target = dir.resolve(UUID.randomUUID() + "." + extension);
            file.transferTo(target);
            return target;
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot store uploaded video", e);
        }
    }

    public void delete(Path path) {
        try {
            Files.deleteIfExists(path);
        } catch (IOException e) {
            log.warn("Cannot delete {}", path, e);
        }
    }

    private String validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new InvalidVideoException("Field 'file' is required and must not be empty");
        }
        if (file.getSize() > maxBytes) {
            throw new InvalidVideoException("File exceeds the limit of " + maxBytes + " bytes");
        }
        String extension = extensionOf(file.getOriginalFilename());
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            throw new InvalidVideoException("Unsupported file type '" + extension + "', expected one of " + ALLOWED_EXTENSIONS);
        }
        return extension;
    }

    private static String extensionOf(String filename) {
        if (filename == null) {
            return "";
        }
        int dot = filename.lastIndexOf('.');
        return dot < 0 ? "" : filename.substring(dot + 1).toLowerCase(Locale.ROOT);
    }
}
