public class Main {
    public static void main(String[] args) {

        String firstName = "Jarda";
        String lastname = "Pospisil";

        cheer (firstName,lastname);

        future("something");

    }

    public static void future(String name) {
        System.out.println("Your future looks like" + name);
    }

    public static void cheer(String firstName, String lastName){
        System.out.println ("Cheer for the " + firstName + " " + lastName);

    }
}
