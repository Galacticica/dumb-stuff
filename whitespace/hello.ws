(Fibonacci_in_Whitespace)(reads_N_prints_first_N_terms_1_1_2_3_5_one_per_line)(read_N_into_heap[1])   	
	
		(seed_a=1)   	
(seed_b=0)   
(label_LOOP)
   
(push_addr_1)   	
(retrieve_N)			(dup) 
 (jz_END_when_N==0)
	 	
(push_1)   	
(N_minus_1)	  	(push_addr_1)   	
(swap) 
	(store_N-1)		 (swap_a_b) 
	(copy_depth_1) 	  	
(add)	   (dup) 
 (output_number)	
 	(push_newline_10)   	 	 
(output_char_sep)	
  (jmp_LOOP)
 
 
(label_END)
  	
(end_program)


