package kz.cashguard.ml;

import java.util.Arrays;
import java.util.Optional;

public enum ViolationType {
    WORKSTATION_UNLOCKED("workstation_unlocked"),
    VALUABLES_LEFT_UNATTENDED("valuables_left_unattended"),
    SAFE_LEFT_OPEN("safe_left_open"),
    CASH_ROOM_DOOR_OPEN("cash_room_door_open"),
    UNAUTHORIZED_ENTRY("unauthorized_entry"),
    CASH_EXPOSED_TO_VISITOR("cash_exposed_to_visitor"),
    CASH_NOT_MACHINE_VERIFIED("cash_not_machine_verified"),
    UNRECOUNTED_CASH_TO_SAFE("unrecounted_cash_to_safe"),
    COUNTING_NOT_IN_CLIENT_PRESENCE("counting_not_in_client_presence"),
    NO_CLIENT_IDENTIFICATION("no_client_identification"),
    COLLECTOR_HANDOVER_UNVERIFIED("collector_handover_unverified"),
    PERSONAL_ITEMS_AT_WORKPLACE("personal_items_at_workplace"),
    FOOD_DRINK_AT_WORKPLACE("food_drink_at_workplace");

    private final String id;

    ViolationType(String id) {
        this.id = id;
    }

    public String id() {
        return id;
    }

    public static Optional<ViolationType> fromId(String id) {
        return Arrays.stream(values()).filter(type -> type.id.equals(id)).findFirst();
    }
}
