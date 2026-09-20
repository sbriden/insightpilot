import { useEffect, useState } from "react";

import {
  getDataProducts,
} from "@/services/api";

import {
  DataProduct,
} from "@/types/report";

import {
  groupProductsByDefinition,
  normalizeProduct,
  ProductGroup,
} from "@/lib/productLineage";


export function useSavedProducts() {

  const [
    products,
    setProducts,
  ] =
    useState<DataProduct[]>([]);

  const [
    groups,
    setGroups,
  ] =
    useState<ProductGroup[]>([]);

  const [
    loaded,
    setLoaded,
  ] =
    useState(false);

  const [
    error,
    setError,
  ] =
    useState<string | null>(null);

  useEffect(() => {

    async function loadProducts() {

      try {

        const result =
          await getDataProducts();

        const normalized =
          Array.isArray(result)
            ? result.map(
                normalizeProduct
              )
            : [];

        setProducts(normalized);

        setGroups(
          groupProductsByDefinition(
            normalized
          )
        );

        setError(null);

      } catch (loadError) {

        console.error(
          "Failed to load saved products:",
          loadError
        );

        setProducts([]);
        setGroups([]);

        setError(
          "Unable to load saved data products."
        );

      } finally {

        setLoaded(true);

      }

    }

    loadProducts();

  }, []);

  return {
    products,
    groups,
    loaded,
    error,
  };

}
