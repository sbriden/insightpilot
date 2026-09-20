import {
    DataProductConfiguration,
  } from "@/types/report";
  
  
  const STORAGE_PREFIX =
    "insightpilot_product_";
  
  
  export function getProductConfiguration(
    productId: string
  ): DataProductConfiguration | null {
  
    if (
      typeof window === "undefined"
    ) {
      return null;
    }
  
    const stored =
      sessionStorage.getItem(
        `${STORAGE_PREFIX}${productId}`
      );
  
    if (!stored) {
      return null;
    }
  
    try {
  
      return JSON.parse(stored);
  
    } catch {
  
      return null;
  
    }
  }
  
  
  export function saveProductConfiguration(
    configuration: DataProductConfiguration
  ) {
  
    sessionStorage.setItem(
      `${STORAGE_PREFIX}${configuration.id}`,
      JSON.stringify(configuration)
    );
  }
  
  
  export function deleteProductConfiguration(
    productId: string
  ) {
  
    sessionStorage.removeItem(
      `${STORAGE_PREFIX}${productId}`
    );
  
  }