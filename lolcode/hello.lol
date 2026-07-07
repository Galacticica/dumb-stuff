HAI 1.2
  CAN HAS STDIO?
  I HAS A previous_number
  I HAS A x
  I HAS A y
  I HAS A input
  x R 0
  y R 1
  VISIBLE "input a number:"
  GIMMEH input


  BOTH SAEM 0 AN input, O RLY?
    YA RLY
      VISIBLE 0
    NO WAI
      IM IN YR label UPPIN YR loop_var WILE BOTH SAEM loop_var AN SMALLR OF loop_var AN DIFF OF input AN 2
          previous_number R y
          y R SUM OF x AN y
          x R previous_number
        IM OUTTA YR label
        VISIBLE y
    OIC
KTHXBYE