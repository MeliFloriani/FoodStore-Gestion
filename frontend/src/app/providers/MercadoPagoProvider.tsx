import React, { useEffect } from "react";
import { initMercadoPago } from "@mercadopago/sdk-react";

type MercadoPagoProviderProps = {
  children: React.ReactNode;
};

export function MercadoPagoProvider({ children }: MercadoPagoProviderProps) {
  useEffect(() => {
    const publicKey = import.meta.env.VITE_MP_PUBLIC_KEY;

    if (!publicKey) {
      console.warn("VITE_MP_PUBLIC_KEY no está configurada");
      return;
    }

    initMercadoPago(publicKey, {
      locale: "es-AR",
    });
  }, []);

  return <>{children}</>;
}