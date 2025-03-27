"use client";

import { useState, useEffect } from "react";
import { Toast, ToastClose, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from "@/components/ui/toast";

// Toast variant types
type ToastVariant = "default" | "destructive" | "success";

interface ToastProps {
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number; // in milliseconds
}

// Hook return type
interface ToastReturn {
  toast: (props: ToastProps) => void;
}

export function useToast(): ToastReturn {
  const [toasts, setToasts] = useState<ToastProps[]>([]);

  const toast = ({ title, description, variant = "default", duration = 3000 }: ToastProps) => {
    setToasts((currentToasts) => [...currentToasts, { title, description, variant, duration }]);
  };

  useEffect(() => {
    if (toasts.length === 0) return;

    const timer = setTimeout(() => {
      setToasts((currentToasts) => currentToasts.slice(1));
    }, toasts[0].duration || 3000);

    return () => clearTimeout(timer);
  }, [toasts]);

  return {
    toast,
  };
}

// ToastProvider component (wrap this around your app or root layout)
export function Toaster() {
  const { toast } = useToast(); // This won't work standalone, so we manage state here too
  const [toasts, setToasts] = useState<ToastProps[]>([]);

  const showToast = ({ title, description, variant = "default", duration = 3000 }: ToastProps) => {
    setToasts((currentToasts) => [...currentToasts, { title, description, variant, duration }]);
  };

  useEffect(() => {
    if (toasts.length === 0) return;

    const timer = setTimeout(() => {
      setToasts((currentToasts) => currentToasts.slice(1));
    }, toasts[0].duration || 3000);

    return () => clearTimeout(timer);
  }, [toasts]);

  return (
    <ToastProvider>
      {toasts.map((t, index) => (
        <Toast key={index} variant={t.variant} className="mb-2">
          {t.title && <ToastTitle>{t.title}</ToastTitle>}
          {t.description && <ToastDescription>{t.description}</ToastDescription>}
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}