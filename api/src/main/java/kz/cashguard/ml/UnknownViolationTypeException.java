package kz.cashguard.ml;

public class UnknownViolationTypeException extends RuntimeException {

    public UnknownViolationTypeException(String typeId) {
        super("ML service returned unknown violation type_id: " + typeId);
    }
}
