module fpCompare_tb;
    reg [31:0] a, b;
    wire [3:0] o;
    wire nanx;
    integer j;

    fpCompare #(32) uut (.a(a), .b(b), .o(o), .nanx(nanx));

    initial begin
        $display("Running robust simulation for fpCompare...");
        
        a = 32'h0; b = 32'h0; #10;
        $display("a=%h | b=%h | o=%b | EQ=%b | LT=%b | MLT=%b | UNO=%b", a, b, o, o[0], o[1], o[2], o[3]);

        a = 32'h40000000; b = 32'h3F800000; #10; // 2.0 vs 1.0
        $display("a=%h | b=%h | o=%b | EQ=%b | LT=%b | MLT=%b | UNO=%b", a, b, o, o[0], o[1], o[2], o[3]);

        for (j = 0; j < 20; j = j + 1) begin
            a = $random;
            b = $random;
            #10;
            $display("a=%h | b=%h | o=%b | nanx=%b", a, b, o, nanx);
        end
        
        $display("fpCompare test finished");
        $finish;
    end
endmodule
