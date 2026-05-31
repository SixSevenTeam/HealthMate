package com.healthmate.medications.repository;

import com.healthmate.medications.entity.Drug;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DrugRepository extends JpaRepository<Drug, UUID> {

    @Query(value = """
        SELECT * FROM medications.drugs d 
        WHERE (
            d.trade_name ILIKE ('%' || :query || '%') OR
            d.international_name ILIKE ('%' || :query || '%') OR
            d.atx_code ILIKE :query OR
            similarity(lower(d.trade_name), lower(:query)) >= 0.22 OR
            similarity(lower(coalesce(d.international_name, '')), lower(:query)) >= 0.22
        )
        ORDER BY GREATEST(
            CASE WHEN d.atx_code ILIKE :query THEN 1.0 ELSE 0.0 END,
            CASE WHEN d.trade_name ILIKE ('%' || :query || '%') THEN 0.95 ELSE 0.0 END,
            CASE WHEN d.international_name ILIKE ('%' || :query || '%') THEN 0.90 ELSE 0.0 END,
            similarity(lower(d.trade_name), lower(:query)),
            similarity(lower(coalesce(d.international_name, '')), lower(:query))
        ) DESC,
        d.is_in_rag DESC,
        d.trade_name
        LIMIT 50
        """, nativeQuery = true)
    List<Drug> searchByQuery(@Param("query") String query);

    Optional<Drug> findByTradeNameIgnoreCase(String tradeName);
}
