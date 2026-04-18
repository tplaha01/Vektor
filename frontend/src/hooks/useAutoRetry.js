import { useState, useCallback } from 'react';
import { useToast } from '../components/common/Toast';

export function useAutoRetry(asyncFunction, maxRetries = 3) {
  const [isRetrying, setIsRetrying] = useState(false);
  const { error: showError } = useToast();
  
  const executeWithRetry = useCallback(async (args = {}, currentAttempt = 1) => {
    try {
      setIsRetrying(false);
      return await asyncFunction(args);
    } catch (err) {
      if (currentAttempt < maxRetries) {
        const delay = Math.pow(2, currentAttempt - 1) * 1000; // Exponential backoff
        setIsRetrying(true);
        await new Promise(resolve => setTimeout(resolve, delay));
        return executeWithRetry(args, currentAttempt + 1);
      } else {
        showError(`Failed after ${maxRetries} attempts: ${err.message}`);
        throw err;
      }
    }
  }, [asyncFunction, maxRetries, showError]);
  
  return { executeWithRetry, isRetrying };
}
