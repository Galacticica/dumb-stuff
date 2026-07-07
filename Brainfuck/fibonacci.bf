,           read one ascii digit into cell 0
>++++++++[<------>-]<     subtract 48 so cell 0 holds N
>>+<<       init cell 2 to one (second fib seed)
[           loop N times
  >>        move to cell 2
  [         copy cell 2 into cell 3 and cell 4
    >+>+<<-
  ]
  >>        restore cell 2 from cell 4
  [
    <<+>>-
  ]
  <<<       add cell 1 into cell 2
  [
    >+<-
  ]
  >>        copy cell 3 into cell 1
  [
    <<+>>-
  ]
  <<<-      back to cell 0 and decrement counter
]
>           result is in cell 1
>[-]++++++++++            set cell 2 to ten as divisor
>[-]>[-]>[-]<<<<          clear scratch cells and return to result
[->-[>+>>]>[+[-<+>]>+>>]<<<<<]    divmod by ten leaving remainder in cell 3 and quotient in cell 4
>>>         move to quotient
[>++++++++[-<++++++>]<.[-]]       print tens digit if nonzero
<           move to remainder
>++++++++[-<++++++>]<.            add 48 and print ones digit
[-]++++++++++.            print newline
